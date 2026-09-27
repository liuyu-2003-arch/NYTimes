import SwiftUI
import WebKit
import Foundation

struct ArticleWebView: UIViewRepresentable {
    let article: Article
    let language: String
    let fontSize: String
    let fontStyle: String
    let store: ArticleStore
    let lookupModel: WordLookupModel
    var highlightWord: String? = nil

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        configuration.userContentController.add(context.coordinator, name: "define")
        configuration.userContentController.addUserScript(
            WKUserScript(source: Coordinator.lookupJS, injectionTime: .atDocumentEnd, forMainFrameOnly: true)
        )
        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator
        webView.backgroundColor = .systemBackground
        webView.isOpaque = false
        context.coordinator.loadArticle(webView: webView)
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        let articleChanged = context.coordinator.loadedArticleID != article.id
        context.coordinator.updateParent(self)
        context.coordinator.updateSettings(language: language, fontSize: fontSize, fontStyle: fontStyle)
        if articleChanged {
            context.coordinator.loadArticle(webView: webView)
        } else if context.coordinator.pageLoaded {
            context.coordinator.applySettings(to: webView)
        }
    }

    @MainActor
    final class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        var parent: ArticleWebView
        var pageLoaded = false
        var language: String
        var fontSize: String
        var fontStyle: String
        var highlightWord: String?
        var loadedArticleID: String?

        init(_ parent: ArticleWebView) {
            self.parent = parent
            self.language = parent.language
            self.fontSize = parent.fontSize
            self.fontStyle = parent.fontStyle
            self.highlightWord = parent.highlightWord
        }

        func updateParent(_ parent: ArticleWebView) {
            self.parent = parent
            self.highlightWord = parent.highlightWord
        }

        func updateSettings(language: String, fontSize: String, fontStyle: String) {
            self.language = language
            self.fontSize = fontSize
            self.fontStyle = fontStyle
        }

        func loadArticle(webView: WKWebView) {
            pageLoaded = false
            loadedArticleID = parent.article.id

            if let localURL = localArticleURL(),
               let data = try? Data(contentsOf: localURL),
               let html = String(data: data, encoding: .utf8) {
                webView.loadHTMLString(
                    removeControls(from: html),
                    baseURL: localURL.deletingLastPathComponent()
                )
                return
            }

            guard let url = parent.article.webURL else {
                displayError("找不到本地文章，且无法生成文章地址。", in: webView)
                return
            }

            let task = URLSession.shared.dataTask(with: url) { [weak self] data, _, _ in
                guard let self = self else { return }
                guard let data = data,
                      let html = String(data: data, encoding: .utf8) else {
                    DispatchQueue.main.async {
                        self.displayError("文章下载失败，请检查网络后重试。", in: webView)
                    }
                    return
                }
                let cleaned = self.removeControls(from: html)
                DispatchQueue.main.async {
                    webView.loadHTMLString(cleaned, baseURL: url.deletingLastPathComponent())
                }
            }
            task.resume()
        }

        private func localArticleURL() -> URL? {
            let components = parent.article.url.split(separator: "/").map(String.init)
            guard components.first == "articles",
                  components.count >= 3,
                  !components.contains("..") else { return nil }

            let url = components.reduce(Bundle.main.bundleURL) { $0.appendingPathComponent($1) }
            return FileManager.default.fileExists(atPath: url.path) ? url : nil
        }

        private func displayError(_ message: String, in webView: WKWebView) {
            let escaped = escapeHTML(message)
            let html = """
            <!doctype html>
            <html>
            <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
            <body style="margin:0;padding:40px 24px;background:#fff;color:#111;font-family:-apple-system,sans-serif;">
                <h2 style="margin-top:0;font-size:22px;">文章载入失败</h2>
                <p style="line-height:1.6;">\(escaped)</p>
            </body>
            </html>
            """
            pageLoaded = false
            webView.loadHTMLString(html, baseURL: nil)
        }

        private func escapeHTML(_ value: String) -> String {
            value
                .replacingOccurrences(of: "&", with: "&amp;")
                .replacingOccurrences(of: "<", with: "&lt;")
                .replacingOccurrences(of: ">", with: "&gt;")
                .replacingOccurrences(of: "\"", with: "&quot;")
                .replacingOccurrences(of: "'", with: "&#39;")
        }

        private nonisolated func removeControls(from html: String) -> String {
            var result = html
            let patterns = [
                "<div class=\"controls-panel\">[\\s\\S]*?</div>\\s*</div>\\s*</div>",
                "<a class=\"back-link\"[\\s\\S]*?</a>",
                "<div class=\"footer-link\">[\\s\\S]*?</div>",
                "<div class=\"controls-right\">[\\s\\S]*?</div>",
            ]
            for pattern in patterns {
                if let regex = try? NSRegularExpression(pattern: pattern, options: []) {
                    let range = NSRange(result.startIndex..., in: result)
                    result = regex.stringByReplacingMatches(in: result, options: [], range: range, withTemplate: "")
                }
            }
            let style = "<style>.controls-panel,.back-link,.footer-link{display:none!important;}.content-container{padding-top:8px!important;padding-bottom:44px!important;}</style>"
            result = result.replacingOccurrences(of: "<head>", with: "<head>\(style)")
            return result
        }

        func applySettings(to webView: WKWebView) {
            let family = fontStyle == "modern"
                ? "-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif"
                : "Georgia,'Times New Roman','Songti SC',serif"
            let size = fontSize == "large" ? 22 : 18

            let js = """
            (function(){
                var fam = \(jsonString(family));
                var lang = \(jsonString(language));
                var style = document.getElementById('app-reader-style');
                if(!style){ style = document.createElement('style'); style.id='app-reader-style'; document.head.appendChild(style); }
                var css = '';
                css += 'html,body{-webkit-transition:none !important;transition:none !important;font-size:\(size)px !important;font-family:' + fam + ' !important;}';
                css += '.article-body,.article-body p,.article-paragraph,.cn-p,.en-p{font-family:' + fam + ' !important;}';
                if(lang === 'en'){ css += '.cn-p{display:none !important;}'; }
                if(lang === 'cn'){ css += '.en-p{display:none !important;}'; }
                style.textContent = css;
            })();
            """
            webView.evaluateJavaScript(js)
        }

        private func jsonString(_ value: String) -> String {
            let data = try? JSONSerialization.data(withJSONObject: [value])
            let array = data.flatMap { String(data: $0, encoding: .utf8) } ?? "[\"\"]"
            return String(array.dropFirst().dropLast())
        }

        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            if navigationAction.navigationType == .linkActivated,
               let url = navigationAction.request.url,
               !url.isFileURL {
                UIApplication.shared.open(url)
                decisionHandler(.cancel)
                return
            }
            decisionHandler(.allow)
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            pageLoaded = true
            applySettings(to: webView)
            if let word = highlightWord {
                webView.evaluateJavaScript(highlightScript(word))
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                    webView.evaluateJavaScript(self.highlightScript(word))
                }
            }
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            displayError(error.localizedDescription, in: webView)
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            displayError(error.localizedDescription, in: webView)
        }

        private func highlightScript(_ word: String) -> String {
            "window.__nytHighlightWord(\(jsonString(word)), true);"
        }

        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            guard message.name == "define", let raw = message.body as? String else { return }
            let word = raw.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            guard !word.isEmpty else { return }
            parent.lookupModel.lookup(word)
        }

        static let lookupJS = """
        (function(){
            if (window.__nytLookupInstalled) return;
            window.__nytLookupInstalled = true;

            var style = document.createElement('style');
            style.textContent = 'body, .article-body, .article-body * { -webkit-user-select: none !important; -webkit-touch-callout: none !important; } '
              + '.nyt-hl { background:#FFE066 !important; color:#111 !important; border-radius:3px; padding:1px 3px; -webkit-box-decoration-break:clone; box-decoration-break:clone; }';
            document.head.appendChild(style);

            function clearHighlight(){
              var nodes = document.querySelectorAll('.nyt-hl');
              for (var i = 0; i < nodes.length; i++) {
                var p = nodes[i].parentNode;
                if (p) { p.replaceChild(document.createTextNode(nodes[i].textContent), nodes[i]); p.normalize(); }
              }
            }
            window.__nytClearHighlight = clearHighlight;

            function applyHighlight(info){
              var node = info.node;
              var text = node.textContent || '';
              var before = text.slice(0, info.start);
              var match = text.slice(info.start, info.end);
              var after = text.slice(info.end);
              var span = document.createElement('span');
              span.className = 'nyt-hl';
              span.textContent = match;
              var parent = node.parentNode;
              if (!parent) return;
              var frag = document.createDocumentFragment();
              if (before) frag.appendChild(document.createTextNode(before));
              frag.appendChild(span);
              if (after) frag.appendChild(document.createTextNode(after));
              parent.replaceChild(frag, node);
            }

            function wordAt(x, y){
              var range = null;
              if (document.caretRangeFromPoint) range = document.caretRangeFromPoint(x, y);
              if (!range || !range.startContainer || range.startContainer.nodeType !== 3) return null;
              var node = range.startContainer;
              var text = node.textContent || '';
              var i = range.startOffset;
              var re = /[A-Za-z'\\-]/;
              var s = i, e = i;
              while (s > 0 && re.test(text[s-1])) s--;
              while (e < text.length && re.test(text[e])) e++;
              var w = text.slice(s, e);
              if (!/^[A-Za-z][A-Za-z'\\-]*$/.test(w) || w.length < 2) return null;
              return { word: w, node: node, start: s, end: e };
            }

            window.__nytHighlightWord = function(word, scroll){
              if (!word) return false;
              clearHighlight();
              var root = document.querySelector('.article-body') || document.body;
              var safe = word.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
              var re = new RegExp('\\\\b' + safe + '\\\\b', 'i');
              var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
              var node;
              while (node = walker.nextNode()){
                var t = node.textContent || '';
                var m = re.exec(t);
                if (m) {
                  applyHighlight({ node: node, start: m.index, end: m.index + m[0].length, word: m[0] });
                  if (scroll) {
                    setTimeout(function(){
                      var el = document.querySelector('.nyt-hl');
                      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }, 250);
                  }
                  return true;
                }
              }
              return false;
            };

            var timer = null, pressFired = false, moved = false, sx = 0, sy = 0;

            document.addEventListener('touchstart', function(e){
              if (e.touches.length !== 1) return;
              var x = e.touches[0].clientX, y = e.touches[0].clientY;
              sx = x; sy = y; moved = false; pressFired = false;
              clearTimeout(timer);
              timer = setTimeout(function(){
                pressFired = true;
                clearHighlight();
                var info = wordAt(x, y);
                if (!info) return;
                applyHighlight(info);
                try { window.webkit.messageHandlers.define.postMessage(info.word); } catch(err) {}
              }, 450);
            }, { passive: true });

            document.addEventListener('touchmove', function(e){
              if (e.touches.length !== 1) return;
              var dx = e.touches[0].clientX - sx;
              var dy = e.touches[0].clientY - sy;
              if (dx * dx + dy * dy > 121) { moved = true; clearTimeout(timer); }
            }, { passive: true });

            document.addEventListener('touchend', function(){
              clearTimeout(timer);
              if (!pressFired && !moved) { clearHighlight(); }
            }, { passive: true });

            document.addEventListener('touchcancel', function(){ clearTimeout(timer); }, { passive: true });
        })();
        """
    }
}

enum DictionaryService {
    static func lookup(_ word: String) async -> LookupResult {
        var phonetic: String?
        var translations: [String] = []
        var examples: [WordExample] = []

        guard let encoded = word.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
              let url = URL(string: "https://dict.youdao.com/jsonapi?q=\(encoded)") else {
            return LookupResult(word: word, phonetic: nil, translations: [], examples: [])
        }

        var request = URLRequest(url: url)
        request.setValue("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15", forHTTPHeaderField: "User-Agent")
        request.timeoutInterval = 12

        do {
            let (data, _) = try await URLSession.shared.data(for: request)
            guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                return LookupResult(word: word, phonetic: nil, translations: [], examples: [])
            }

            if let ec = json["ec"] as? [String: Any],
               let words = ec["word"] as? [[String: Any]],
               let first = words.first {
                if let us = first["usphone"] as? String, !us.isEmpty {
                    phonetic = "/\(us)/"
                } else if let uk = first["ukphone"] as? String, !uk.isEmpty {
                    phonetic = "/\(uk)/"
                }

                if let trs = first["trs"] as? [[String: Any]] {
                    for tr in trs {
                        guard let items = tr["tr"] as? [[String: Any]] else { continue }
                        for item in items {
                            guard let l = item["l"] as? [String: Any],
                                  let lines = l["i"] as? [String] else { continue }
                            for line in lines {
                                let cleaned = line.trimmingCharacters(in: .whitespacesAndNewlines)
                                if !cleaned.isEmpty { translations.append(cleaned) }
                            }
                        }
                    }
                }
            }

            if let part = json["blng_sents_part"] as? [String: Any],
               let pairs = part["sentence-pair"] as? [[String: Any]] {
                for pair in pairs {
                    guard let en = pair["sentence"] as? String else { continue }
                    let zh = (pair["sentence-translation"] as? String).map { stripTags($0) }
                    examples.append(WordExample(en: stripTags(en), zh: zh))
                    if examples.count >= 4 { break }
                }
            }
        } catch {
            return LookupResult(word: word, phonetic: nil, translations: [], examples: [])
        }

        return LookupResult(word: word, phonetic: phonetic, translations: translations, examples: examples)
    }

    private static func stripTags(_ value: String) -> String {
        value.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
