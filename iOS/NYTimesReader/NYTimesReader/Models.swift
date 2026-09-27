import Foundation
import AVFoundation

@MainActor
final class SpeechService {
    static let shared = SpeechService()
    private let synthesizer = AVSpeechSynthesizer()

    func speak(_ text: String, language: String = "en-US") {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio, options: [.duckOthers])
        try? AVAudioSession.sharedInstance().setActive(true)

        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking(at: .immediate)
        }

        let utterance = AVSpeechUtterance(string: trimmed)
        utterance.voice = AVSpeechSynthesisVoice(language: language)
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate * 0.9
        utterance.pitchMultiplier = 1.0
        synthesizer.speak(utterance)
    }
}

struct Article: Codable, Hashable, Identifiable {
    let titleCN: String
    let titleEN: String
    let url: String
    let date: String
    let tag: String

    var id: String { url }

    var webURL: URL? {
        let base = "https://nytimes.324893.xyz"
        return URL(string: "\(base)/\(url)")
    }

    enum CodingKeys: String, CodingKey {
        case titleCN = "title_cn"
        case titleEN = "title_en"
        case url, date, tag
    }
}

struct WordExample: Codable, Hashable {
    let en: String
    let zh: String?
}

struct LookupResult: Equatable {
    let word: String
    let phonetic: String?
    let translations: [String]
    let examples: [WordExample]
}

struct LookupRequest: Identifiable, Equatable {
    let id = UUID()
    let word: String
}

@MainActor
final class WordLookupModel: ObservableObject {
    @Published var request: LookupRequest?
    @Published private(set) var result: LookupResult?
    @Published private(set) var isLoading = false

    private var cache: [String: LookupResult] = [:]

    func lookup(_ rawWord: String) {
        let word = rawWord.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !word.isEmpty else { return }
        request = LookupRequest(word: word)

        if let cached = cache[word] {
            result = cached
            isLoading = false
            return
        }

        result = nil
        isLoading = true
        Task { [weak self] in
            guard let self = self else { return }
            let fetched = await DictionaryService.lookup(word)
            self.cache[word] = fetched
            if self.request?.word == word {
                self.result = fetched
                self.isLoading = false
            }
        }
    }
}

struct SavedWord: Codable, Hashable, Identifiable {
    let word: String
    var phonetic: String?
    var translation: String
    var examples: [WordExample]
    var dateAdded: Date
    var reviewCount: Int
    var lastReviewed: Date?
    var sourceURL: String?
    var sourceTitle: String?

    var id: String { word }
}

private struct UserDataBackup: Codable {
    var favoriteURLs: [String]
    var savedWords: [SavedWord]
    var searchHistory: [String]
}

@MainActor
final class ArticleStore: ObservableObject {
    enum RefreshOutcome {
        case updated(count: Int)
        case unchanged(count: Int)
        case failed(String)
    }

    @Published private(set) var articles: [Article] = []
    @Published private(set) var favoriteURLs: Set<String> = []
    @Published private(set) var searchHistory: [String] = []
    @Published private(set) var savedWords: [SavedWord] = []
    @Published private(set) var loadError: String?

    private let favoritesKey = "favoriteArticleURLs"
    private let searchHistoryKey = "searchHistory"
    private let savedWordsKey = "savedWords"
    private let userDataFileName = "user-data.json"

    init() {
        loadFavorites()
        loadSearchHistory()
        loadSavedWords()
        persistUserData()
        loadArticles()
    }

    func isFavorite(_ article: Article) -> Bool {
        favoriteURLs.contains(article.url)
    }

    func toggleFavorite(_ article: Article) {
        if favoriteURLs.contains(article.url) {
            favoriteURLs.remove(article.url)
        } else {
            favoriteURLs.insert(article.url)
        }
        persistUserData()
    }

    func addSearchTerm(_ term: String) {
        let trimmed = term.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        searchHistory.removeAll { $0.caseInsensitiveCompare(trimmed) == .orderedSame }
        searchHistory.insert(trimmed, at: 0)
        if searchHistory.count > 20 {
            searchHistory = Array(searchHistory.prefix(20))
        }
        persistUserData()
    }

    func removeSearchTerm(_ term: String) {
        searchHistory.removeAll { $0 == term }
        persistUserData()
    }

    func clearSearchHistory() {
        searchHistory.removeAll()
        persistUserData()
    }

    func search(_ query: String) -> [Article] {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return [] }
        let normalizedQuery = ArticleStore.normalizeChinese(trimmed)
        return articles.filter {
            ArticleStore.normalizeChinese($0.titleCN).localizedCaseInsensitiveContains(normalizedQuery) ||
            $0.titleEN.localizedCaseInsensitiveContains(trimmed)
        }
    }

    static func normalizeChinese(_ text: String) -> String {
        text.applyingTransform(StringTransform("Traditional-Simplified"), reverse: false) ?? text
    }

    func article(for url: String?) -> Article? {
        guard let url = url else { return nil }
        return articles.first { $0.url == url }
    }

    func isSaved(_ word: String) -> Bool {
        savedWords.contains { $0.word.caseInsensitiveCompare(word) == .orderedSame }
    }

    func saveWord(_ word: SavedWord) {
        guard !isSaved(word.word) else { return }
        savedWords.insert(word, at: 0)
        persistUserData()
    }

    func removeWord(_ word: String) {
        savedWords.removeAll { $0.word.caseInsensitiveCompare(word) == .orderedSame }
        persistUserData()
    }

    func markReviewed(_ word: String) {
        guard let index = savedWords.firstIndex(where: { $0.word == word }) else { return }
        savedWords[index].reviewCount += 1
        savedWords[index].lastReviewed = Date()
        persistUserData()
    }

    private var userDataBackupURL: URL? {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)
            .first?
            .appendingPathComponent(userDataFileName)
    }

    private func loadSavedWords() {
        let storedWords: [SavedWord]
        if let data = UserDefaults.standard.data(forKey: savedWordsKey),
           let words = try? JSONDecoder().decode([SavedWord].self, from: data) {
            storedWords = words
        } else {
            storedWords = []
        }

        savedWords = Self.mergeSavedWords(storedWords, readUserDataBackup()?.savedWords ?? [])
    }

    private func loadFavorites() {
        let storedFavorites = UserDefaults.standard.stringArray(forKey: favoritesKey) ?? []
        let backupFavorites = readUserDataBackup()?.favoriteURLs ?? []
        favoriteURLs = Set(storedFavorites + backupFavorites)
    }

    private func loadSearchHistory() {
        let storedHistory = UserDefaults.standard.stringArray(forKey: searchHistoryKey) ?? []
        let backupHistory = readUserDataBackup()?.searchHistory ?? []
        var seen = Set<String>()
        searchHistory = (storedHistory + backupHistory)
            .filter { seen.insert($0.lowercased()).inserted }
            .prefix(20)
            .map { $0 }
    }

    private func readUserDataBackup() -> UserDataBackup? {
        guard let url = userDataBackupURL,
              let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(UserDataBackup.self, from: data)
    }

    private func persistUserData() {
        UserDefaults.standard.set(Array(favoriteURLs).sorted(), forKey: favoritesKey)
        UserDefaults.standard.set(searchHistory, forKey: searchHistoryKey)
        if let data = try? JSONEncoder().encode(savedWords) {
            UserDefaults.standard.set(data, forKey: savedWordsKey)
        }

        let backup = UserDataBackup(
            favoriteURLs: Array(favoriteURLs).sorted(),
            savedWords: savedWords,
            searchHistory: searchHistory
        )
        guard let url = userDataBackupURL,
              let data = try? JSONEncoder().encode(backup) else { return }
        try? data.write(to: url, options: .atomic)
    }

    private static func mergeSavedWords(_ first: [SavedWord], _ second: [SavedWord]) -> [SavedWord] {
        var wordsByKey: [String: SavedWord] = [:]

        for word in first + second {
            let key = word.word.lowercased()
            guard let existing = wordsByKey[key] else {
                wordsByKey[key] = word
                continue
            }

            let preferred = word.dateAdded >= existing.dateAdded ? word : existing
            let fallback = word.dateAdded >= existing.dateAdded ? existing : word
            var merged = preferred
            merged.phonetic = preferred.phonetic ?? fallback.phonetic
            if merged.translation.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                merged.translation = fallback.translation
            }
            if merged.examples.isEmpty {
                merged.examples = fallback.examples
            }
            merged.reviewCount = max(preferred.reviewCount, fallback.reviewCount)
            merged.lastReviewed = [preferred.lastReviewed, fallback.lastReviewed].compactMap { $0 }.max()
            merged.sourceURL = preferred.sourceURL ?? fallback.sourceURL
            merged.sourceTitle = preferred.sourceTitle ?? fallback.sourceTitle
            wordsByKey[key] = merged
        }

        return wordsByKey.values.sorted { $0.dateAdded > $1.dateAdded }
    }

    @discardableResult
    func refreshArticles() async -> RefreshOutcome {
        await fetchLatestArticles()
    }

    private func loadArticles() {
        if let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
            let cachedURL = dir.appendingPathComponent("articles.json")
            if let data = try? Data(contentsOf: cachedURL),
               let cached = try? JSONDecoder().decode([Article].self, from: data),
               !cached.isEmpty {
                articles = cached
                Task { _ = await fetchLatestArticles() }
                return
            }
        }

        guard let fileURL = Bundle.main.url(forResource: "articles", withExtension: "json") else {
            loadError = "找不到内置文章索引。"
            return
        }

        do {
            let data = try Data(contentsOf: fileURL)
            articles = try JSONDecoder().decode([Article].self, from: data)
        } catch {
            loadError = "无法读取文章索引：\(error.localizedDescription)"
        }

        Task { _ = await fetchLatestArticles() }
    }

    private func fetchLatestArticles() async -> RefreshOutcome {
        guard let url = URL(string: "https://nytimes.324893.xyz/articles.json") else {
            return .failed("文章地址无效")
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            if let http = response as? HTTPURLResponse,
               !(200...299).contains(http.statusCode) {
                return .failed("服务器返回 HTTP \(http.statusCode)")
            }
            let fetched = try JSONDecoder().decode([Article].self, from: data)
            guard !fetched.isEmpty else {
                return .failed("服务器返回的文章列表为空")
            }

            if fetched == articles {
                return .unchanged(count: articles.count)
            }

            articles = fetched
            cacheArticles(data)
            return .updated(count: fetched.count)
        } catch {
            return .failed(error.localizedDescription)
        }
    }

    private func cacheArticles(_ data: Data) {
        guard let fileURL = FileManager.default.urls(
            for: .documentDirectory,
            in: .userDomainMask
        ).first?.appendingPathComponent("articles.json") else { return }
        try? data.write(to: fileURL, options: .atomic)
    }
}
