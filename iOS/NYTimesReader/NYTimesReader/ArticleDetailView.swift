import SwiftUI

struct ArticleDetailView: View {
    @EnvironmentObject private var store: ArticleStore
    let article: Article
    var highlightWord: String? = nil
    @AppStorage("readerLanguage") private var language = "dual"
    @AppStorage("readerFontSize") private var fontSize = "normal"
    @AppStorage("readerFontStyle") private var fontStyle = "serif"
    @State private var showSettings = false
    @StateObject private var lookup = WordLookupModel()

    private var effectiveLanguage: String {
        if highlightWord != nil && language == "cn" { return "dual" }
        return language
    }

    var body: some View {
        ArticleWebView(
            article: article,
            language: effectiveLanguage,
            fontSize: fontSize,
            fontStyle: fontStyle,
            store: store,
            lookupModel: lookup,
            highlightWord: highlightWord
        )
        .ignoresSafeArea(edges: .bottom)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button {
                    store.toggleFavorite(article)
                } label: {
                    Image(systemName: store.isFavorite(article) ? "bookmark.fill" : "bookmark")
                }

                Button {
                    showSettings = true
                } label: {
                    Image(systemName: "textformat")
                }
            }
        }
        .sheet(isPresented: $showSettings) {
            settingsSheet
        }
        .sheet(item: $lookup.request) { request in
            WordLookupView(model: lookup, word: request.word, sourceArticle: article)
                .environmentObject(store)
        }
    }

    private var settingsSheet: some View {
        NavigationStack {
            List {
                Section("显示语言") {
                    ForEach([("dual", "中英对照"), ("en", "仅英文"), ("cn", "仅中文")], id: \.0) { value, label in
                        Button {
                            language = value
                        } label: {
                            HStack {
                                Text(label)
                                    .foregroundStyle(.primary)
                                Spacer()
                                if language == value {
                                    Image(systemName: "checkmark")
                                        .foregroundStyle(.red)
                                }
                            }
                        }
                    }
                }

                Section("字号") {
                    ForEach([("normal", "标准"), ("large", "大号")], id: \.0) { value, label in
                        Button {
                            fontSize = value
                        } label: {
                            HStack {
                                Text(label)
                                    .foregroundStyle(.primary)
                                Spacer()
                                if fontSize == value {
                                    Image(systemName: "checkmark")
                                        .foregroundStyle(.red)
                                }
                            }
                        }
                    }
                }

                Section("字体") {
                    ForEach([("serif", "衬线体"), ("modern", "现代体")], id: \.0) { value, label in
                        Button {
                            fontStyle = value
                        } label: {
                            HStack {
                                Text(label)
                                    .foregroundStyle(.primary)
                                Spacer()
                                if fontStyle == value {
                                    Image(systemName: "checkmark")
                                        .foregroundStyle(.red)
                                }
                            }
                        }
                    }
                }
            }
            .navigationTitle("阅读设置")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("完成") {
                        showSettings = false
                    }
                }
            }
        }
        .presentationDetents([.medium])
    }
}

struct WordLookupView: View {
    @EnvironmentObject private var store: ArticleStore
    @ObservedObject var model: WordLookupModel
    @Environment(\.dismiss) private var dismiss
    let word: String
    let sourceArticle: Article

    var body: some View {
        NavigationStack {
            Group {
                if model.isLoading {
                    VStack(spacing: 14) {
                        ProgressView()
                        Text("查询中…")
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let result = model.result {
                    content(result)
                } else {
                    ContentUnavailableView(
                        "未找到释义",
                        systemImage: "character.book.closed",
                        description: Text("换个词或检查网络后重试")
                    )
                }
            }
            .navigationTitle(word)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("完成") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }

    @ViewBuilder
    private func content(_ result: LookupResult) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    Text(result.word)
                        .font(.largeTitle.bold())
                    Button {
                        SpeechService.shared.speak(result.word)
                    } label: {
                        Image(systemName: "speaker.wave.2.fill")
                            .font(.title3)
                            .foregroundStyle(.red)
                    }
                    .buttonStyle(.borderless)
                    if let phonetic = result.phonetic {
                        Text(phonetic)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }

                ForEach(Array(result.translations.enumerated()), id: \.offset) { _, line in
                    Text(line)
                        .font(.body.weight(.semibold))
                        .foregroundStyle(.blue)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                Button {
                    saveWord(result)
                } label: {
                    if store.isSaved(result.word) {
                        Label("已加入单词本", systemImage: "star.fill")
                    } else {
                        Label("加入单词本", systemImage: "star")
                    }
                }
                .buttonStyle(.bordered)
                .disabled(store.isSaved(result.word))

                if !result.examples.isEmpty {
                    Divider()
                    Text("例句")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(.secondary)
                        .textCase(.uppercase)
                    ForEach(Array(result.examples.enumerated()), id: \.offset) { _, example in
                        VStack(alignment: .leading, spacing: 3) {
                            Text(example.en)
                                .font(.callout)
                            if let zh = example.zh {
                                Text(zh)
                                    .font(.footnote)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(20)
        }
    }

    private func saveWord(_ result: LookupResult) {
        let saved = SavedWord(
            word: result.word,
            phonetic: result.phonetic,
            translation: result.translations.joined(separator: "\n"),
            examples: result.examples,
            dateAdded: Date(),
            reviewCount: 0,
            lastReviewed: nil,
            sourceURL: sourceArticle.url,
            sourceTitle: sourceArticle.titleCN
        )
        store.saveWord(saved)
    }
}
