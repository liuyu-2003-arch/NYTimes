import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var store: ArticleStore
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            ArticleListView(title: "双语头条", articles: store.articles)
                .tabItem { Label("新闻", systemImage: "newspaper") }
                .tag(0)

            ArticleListView(
                title: "收藏",
                articles: store.articles.filter(store.isFavorite),
                emptyMessage: "还没有收藏文章"
            )
            .tabItem { Label("收藏", systemImage: "bookmark") }
            .tag(1)

            WordBookView()
                .tabItem { Label("单词", systemImage: "character.book.closed") }
                .tag(2)

            SettingsView()
                .tabItem { Label("设置", systemImage: "gearshape") }
                .tag(3)
        }
        .tint(.red)
    }
}

struct ArticleListView: View {
    @EnvironmentObject private var store: ArticleStore
    let title: String
    let articles: [Article]
    var emptyMessage = "暂无文章"
    @State private var selectedDate: Date? = nil
    @State private var showDatePicker = false
    @State private var showSearch = false
    @State private var currentPage = 0
    @State private var showPagination = false
    private let pageSize = 10

    private var filteredArticles: [Article] {
        guard let date = selectedDate else { return articles }
        let df = DateFormatter()
        df.dateFormat = "yyyy-MM-dd"
        let dateStr = df.string(from: date)
        return articles.filter { $0.date == dateStr }
    }

    private var totalPages: Int {
        max(1, Int(ceil(Double(filteredArticles.count) / Double(pageSize))))
    }

    private var pagedArticles: [Article] {
        let start = currentPage * pageSize
        guard start < filteredArticles.count else { return [] }
        let end = min(start + pageSize, filteredArticles.count)
        return Array(filteredArticles[start..<end])
    }

    private var articleDateCounts: [String: Int] {
        Dictionary(grouping: articles, by: \.date).mapValues(\.count)
    }

    private func dateLabel(_ date: Date) -> String {
        let df = DateFormatter()
        df.dateFormat = "M月d日"
        return df.string(from: date)
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                HStack(spacing: 20) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(title)
                            .font(.largeTitle.bold())
                        if let date = selectedDate {
                            HStack(spacing: 10) {
                                Text(dateLabel(date))
                                    .font(.subheadline.weight(.semibold))
                                    .foregroundStyle(.red)
                                Button {
                                    withAnimation(.easeInOut(duration: 0.2)) { selectedDate = nil }
                                } label: {
                                    Text("显示全部")
                                        .font(.subheadline)
                                        .foregroundStyle(.secondary)
                                }
                            }
                            .transition(.opacity.combined(with: .move(edge: .top)))
                        }
                    }
                    Spacer()
                    Button {
                        showSearch = true
                    } label: {
                        Image(systemName: "magnifyingglass")
                            .font(.title2)
                            .foregroundStyle(.primary)
                    }
                    Button {
                        withAnimation(.spring(response: 0.35, dampingFraction: 0.82)) {
                            showDatePicker = true
                        }
                    } label: {
                        Image(systemName: selectedDate != nil ? "calendar.circle.fill" : "calendar")
                            .font(.title2)
                            .foregroundStyle(.primary)
                    }
                }
                .padding(.leading, 30)
                .padding(.trailing, 22)
                .padding(.top, 26)
                .padding(.bottom, 8)

                Group {
                    if let error = store.loadError {
                        ContentUnavailableView("无法载入新闻", systemImage: "exclamationmark.triangle", description: Text(error))
                    } else if filteredArticles.isEmpty {
                        ContentUnavailableView(emptyMessage, systemImage: "newspaper")
                    } else {
                        List {
                            ForEach(pagedArticles) { article in
                                ZStack {
                                    NavigationLink(value: article) { EmptyView() }.opacity(0).buttonStyle(.plain)
                                    ArticleRow(article: article)
                                }
                                .listRowInsets(EdgeInsets(top: 5, leading: 4, bottom: 5, trailing: 4))
                                .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                    Button {
                                        store.toggleFavorite(article)
                                    } label: {
                                        Label(store.isFavorite(article) ? "取消收藏" : "收藏", systemImage: store.isFavorite(article) ? "bookmark.slash" : "bookmark")
                                    }
                                    .tint(.orange)
                                }
                            }

                            Color.clear
                                .frame(height: 1)
                                .listRowSeparator(.hidden)
                                .listRowInsets(EdgeInsets())
                                .onAppear {
                                    withAnimation(.easeInOut(duration: 0.2)) { showPagination = true }
                                }
                                .onDisappear {
                                    withAnimation(.easeInOut(duration: 0.2)) { showPagination = false }
                                }
                        }
                        .id(currentPage)
                        .listStyle(.insetGrouped)
                        .listSectionSpacing(0)
                        .scrollContentBackground(.hidden)
                    }
                }
            }
            .navigationBarHidden(true)
            .navigationDestination(for: Article.self) { article in
                ArticleDetailView(article: article)
            }
            .overlay(alignment: .bottom) {
                if showPagination && totalPages > 1 && !filteredArticles.isEmpty {
                    HStack(spacing: 30) {
                        Button {
                            withAnimation { currentPage = max(0, currentPage - 1) }
                        } label: {
                            Image(systemName: "chevron.left")
                                .font(.title3.weight(.bold))
                                .frame(width: 64, height: 48)
                                .background(Color(.secondarySystemBackground))
                                .clipShape(Capsule())
                        }
                        .disabled(currentPage == 0)
                        .opacity(currentPage == 0 ? 0.4 : 1)

                        Text("\(currentPage + 1) / \(totalPages)")
                            .font(.headline)
                            .foregroundStyle(.secondary)
                            .monospacedDigit()

                        Button {
                            withAnimation { currentPage = min(totalPages - 1, currentPage + 1) }
                        } label: {
                            Image(systemName: "chevron.right")
                                .font(.title3.weight(.bold))
                                .frame(width: 64, height: 48)
                                .background(Color(.secondarySystemBackground))
                                .clipShape(Capsule())
                        }
                        .disabled(currentPage >= totalPages - 1)
                        .opacity(currentPage >= totalPages - 1 ? 0.4 : 1)
                    }
                    .padding(.horizontal, 20)
                    .padding(.vertical, 8)
                    .background(.ultraThinMaterial)
                    .clipShape(Capsule())
                    .shadow(color: .black.opacity(0.12), radius: 10, y: 4)
                    .padding(.bottom, 10)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .overlay {
                if showDatePicker {
                    ZStack {
                        Color.black.opacity(0.4)
                            .ignoresSafeArea()
                            .onTapGesture {
                                withAnimation(.easeOut(duration: 0.2)) { showDatePicker = false }
                            }
                            .transition(.opacity)
                        CalendarSheet(
                            dateCounts: articleDateCounts,
                            selectedDate: $selectedDate,
                            isPresented: $showDatePicker
                        )
                        .background(Color(.systemBackground))
                        .clipShape(RoundedRectangle(cornerRadius: 26, style: .continuous))
                        .padding(.horizontal, 34)
                        .shadow(color: .black.opacity(0.25), radius: 30, y: 14)
                        .transition(.scale(scale: 0.88).combined(with: .opacity))
                    }
                }
            }
            .sheet(isPresented: $showSearch) {
                SearchView()
            }
            .onChange(of: selectedDate) { _, _ in
                currentPage = 0
                showPagination = false
            }
        }
    }
}

struct CalendarSheet: View {
    let dateCounts: [String: Int]
    @Binding var selectedDate: Date?
    @Binding var isPresented: Bool
    @State private var month = Date()
    @State private var slideForward = true

    private let calendar = Calendar.current
    private let df: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    private var monthTitle: String {
        let f = DateFormatter()
        f.dateFormat = "yyyy年M月"
        return f.string(from: month)
    }

    private var days: [Date?] {
        guard let range = calendar.range(of: .day, in: .month, for: month),
              let first = calendar.date(from: calendar.dateComponents([.year, .month], from: month))
        else { return [] }
        let weekday = calendar.component(.weekday, from: first)
        let offset = (weekday - calendar.firstWeekday + 7) % 7
        var result: [Date?] = Array(repeating: nil, count: offset)
        for d in range {
            if let date = calendar.date(byAdding: .day, value: d - 1, to: first) {
                result.append(date)
            }
        }
        while result.count < 42 { result.append(nil) }
        return result
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Button { move(-1) } label: {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(.red)
                        .frame(width: 34, height: 34)
                        .background(Color.red.opacity(0.1))
                        .clipShape(Circle())
                }
                Spacer()
                Text(monthTitle)
                    .font(.system(size: 18, weight: .bold))
                Spacer()
                Button { move(1) } label: {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(.red)
                        .frame(width: 34, height: 34)
                        .background(Color.red.opacity(0.1))
                        .clipShape(Circle())
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 16)
            .padding(.bottom, 12)

            Divider().padding(.horizontal, 16)

            HStack(spacing: 0) {
                ForEach(["日","一","二","三","四","五","六"], id: \.self) {
                    Text($0)
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity)
                }
            }
            .padding(.horizontal, 8)
            .padding(.top, 12)
            .padding(.bottom, 4)

            ZStack {
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 0), count: 7), spacing: 2) {
                    ForEach(Array(days.enumerated()), id: \.offset) { _, date in
                        if let date = date {
                            dayCell(date)
                        } else {
                            Color.clear.frame(height: 46)
                        }
                    }
                }
                .id(month)
                .transition(.asymmetric(
                    insertion: .move(edge: slideForward ? .trailing : .leading).combined(with: .opacity),
                    removal: .move(edge: slideForward ? .leading : .trailing).combined(with: .opacity)
                ))
            }
            .padding(.horizontal, 8)
            .padding(.bottom, 6)
            .clipped()

            Divider().padding(.horizontal, 16)

            HStack {
                if selectedDate != nil {
                    Button {
                        selectedDate = nil
                        isPresented = false
                    } label: {
                        Label("显示全部", systemImage: "arrow.counterclockwise")
                            .font(.system(size: 14, weight: .medium))
                    }
                    .foregroundStyle(.red)
                } else {
                    Text("仅可选择有文章的日期")
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button {
                    isPresented = false
                } label: {
                    Text("关闭")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 13)
        }
        .background(Color(.systemBackground))
    }

    @ViewBuilder
    private func dayCell(_ date: Date) -> some View {
        let key = df.string(from: date)
        let count = dateCounts[key] ?? 0
        let active = count > 0
        let isSelected = selectedDate.map { calendar.isDate($0, inSameDayAs: date) } ?? false
        let isToday = calendar.isDateInToday(date)

        Button {
            withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                selectedDate = date
            }
            isPresented = false
        } label: {
            VStack(spacing: 1) {
                Text("\(calendar.component(.day, from: date))")
                    .font(.system(size: 16, weight: isSelected || isToday ? .bold : .regular))
                    .foregroundStyle(isSelected ? Color.white : (active ? Color.primary : Color(.tertiaryLabel)))
                    .frame(width: 34, height: 34)
                    .background {
                        if isSelected {
                            Circle().fill(Color.red)
                        } else if isToday {
                            Circle().stroke(Color.red, lineWidth: 1.5)
                        }
                    }
                if active {
                    Text("\(count)")
                        .font(.system(size: 9, weight: .semibold))
                        .foregroundStyle(.red)
                } else {
                    Text(" ").font(.system(size: 9))
                }
            }
            .frame(height: 46)
            .contentShape(Rectangle())
        }
        .buttonStyle(DayCellButtonStyle())
        .disabled(!active)
    }

    private func move(_ offset: Int) {
        guard let d = calendar.date(byAdding: .month, value: offset, to: month) else { return }
        slideForward = offset > 0
        withAnimation(.easeInOut(duration: 0.28)) {
            month = d
        }
    }
}

struct DayCellButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.85 : 1)
            .animation(.spring(response: 0.25, dampingFraction: 0.6), value: configuration.isPressed)
    }
}

struct SettingsView: View {
    @EnvironmentObject private var store: ArticleStore
    @AppStorage("readerLanguage") private var language = "dual"
    @AppStorage("readerFontSize") private var fontSize = "normal"
    @AppStorage("readerFontStyle") private var fontStyle = "serif"
    @State private var isRefreshing = false
    @State private var refreshMessage: String?
    @State private var refreshFailed = false

    private var appVersion: String {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "未知"
        let build = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "未知"
        return "\(version) (\(build))"
    }

    var body: some View {
        NavigationStack {
            List {
                Section("阅读设置") {
                    Picker("显示语言", selection: $language) {
                        Text("中英对照").tag("dual")
                        Text("仅英文").tag("en")
                        Text("仅中文").tag("cn")
                    }
                    Picker("字号", selection: $fontSize) {
                        Text("标准").tag("normal")
                        Text("大号").tag("large")
                    }
                    Picker("字体", selection: $fontStyle) {
                        Text("衬线体").tag("serif")
                        Text("现代体").tag("modern")
                    }
                }

                Section("数据") {
                    Button {
                        Task {
                            isRefreshing = true
                            refreshMessage = nil
                            refreshFailed = false
                            let outcome = await store.refreshArticles()
                            isRefreshing = false
                            switch outcome {
                            case .updated(let count):
                                refreshMessage = "已更新，共 \(count) 篇"
                            case .unchanged(let count):
                                refreshMessage = "已是最新，共 \(count) 篇"
                            case .failed(let reason):
                                refreshFailed = true
                                refreshMessage = "更新失败：\(reason)"
                            }
                        }
                    } label: {
                        HStack {
                            Label("刷新文章", systemImage: "arrow.clockwise")
                            Spacer()
                            if isRefreshing {
                                ProgressView()
                            } else if let msg = refreshMessage {
                                Text(msg)
                                    .font(.footnote)
                                    .foregroundStyle(refreshFailed ? Color.red : Color.secondary)
                                    .multilineTextAlignment(.trailing)
                            }
                        }
                    }
                    .disabled(isRefreshing)

                    Button(role: .destructive) {
                        store.clearSearchHistory()
                    } label: {
                        Label("清除搜索记录", systemImage: "clock.arrow.circlepath")
                    }
                }

                Section("关于") {
                    HStack {
                        Text("文章总数")
                        Spacer()
                        Text("\(store.articles.count)").foregroundStyle(.secondary)
                    }
                    HStack {
                        Text("单词本")
                        Spacer()
                        Text("\(store.savedWords.count)").foregroundStyle(.secondary)
                    }
                    HStack {
                        Text("版本")
                        Spacer()
                        Text(appVersion).foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("设置")
        }
    }
}

struct SearchView: View {
    @EnvironmentObject private var store: ArticleStore
    @Environment(\.dismiss) private var dismiss
    @State private var query = ""

    private var results: [Article] {
        store.search(query)
    }

    var body: some View {
        NavigationStack {
            List {
                if query.isEmpty {
                    if store.searchHistory.isEmpty {
                        Section {
                            ContentUnavailableView(
                                "搜索文章",
                                systemImage: "magnifyingglass",
                                description: Text("输入中文或英文标题关键词")
                            )
                        }
                    } else {
                        Section {
                            ForEach(store.searchHistory, id: \.self) { term in
                                Button {
                                    query = term
                                } label: {
                                    HStack {
                                        Image(systemName: "clock.arrow.circlepath")
                                            .foregroundStyle(.secondary)
                                        Text(term)
                                            .foregroundStyle(.primary)
                                        Spacer()
                                        Button {
                                            store.removeSearchTerm(term)
                                        } label: {
                                            Image(systemName: "xmark")
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        }
                                        .buttonStyle(.plain)
                                    }
                                }
                                .swipeActions(edge: .trailing) {
                                    Button(role: .destructive) {
                                        store.removeSearchTerm(term)
                                    } label: {
                                        Label("删除", systemImage: "trash")
                                    }
                                }
                            }
                        } header: {
                            HStack {
                                Text("搜索记录")
                                Spacer()
                                Button("清除") {
                                    store.clearSearchHistory()
                                }
                                .font(.caption)
                                .textCase(nil)
                            }
                        }
                    }
                } else if results.isEmpty {
                    Section {
                        ContentUnavailableView.search(text: query)
                    }
                } else {
                    Section("找到 \(results.count) 篇文章") {
                            ForEach(results) { article in
                                ZStack {
                                    NavigationLink(value: article) { EmptyView() }.opacity(0).buttonStyle(.plain)
                                    ArticleRow(article: article)
                                }
                            }
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("搜索")
            .navigationBarTitleDisplayMode(.inline)
            .navigationDestination(for: Article.self) { article in
                ArticleDetailView(article: article)
            }
            .searchable(text: $query, prompt: "搜索中文或英文标题")
            .onSubmit(of: .search) {
                store.addSearchTerm(query)
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("完成") { dismiss() }
                }
            }
        }
    }
}

struct WordBookView: View {
    @EnvironmentObject private var store: ArticleStore
    @State private var showReview = false
    @State private var selectedWord: SavedWord?

    var body: some View {
        NavigationStack {
            Group {
                if store.savedWords.isEmpty {
                    ContentUnavailableView(
                        "单词本为空",
                        systemImage: "character.book.closed",
                        description: Text("阅读文章时长按英文单词，即可加入单词本")
                    )
                } else {
                    List {
                        ForEach(store.savedWords) { word in
                            HStack(spacing: 8) {
                                Button {
                                    selectedWord = word
                                } label: {
                                    WordRow(word: word)
                                }
                                .buttonStyle(.plain)

                                Button {
                                    SpeechService.shared.speak(word.word)
                                } label: {
                                    Image(systemName: "speaker.wave.2.fill")
                                        .font(.system(size: 15))
                                        .foregroundStyle(.red)
                                        .frame(width: 40, height: 40)
                                        .contentShape(Rectangle())
                                }
                                .buttonStyle(.borderless)
                            }
                            .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                Button(role: .destructive) {
                                    store.removeWord(word.word)
                                } label: {
                                    Label("删除", systemImage: "trash")
                                }
                            }
                        }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("单词本")
            .toolbar {
                if !store.savedWords.isEmpty {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            showReview = true
                        } label: {
                            Label("复习", systemImage: "rectangle.stack")
                        }
                    }
                }
            }
            .sheet(item: $selectedWord) { word in
                WordDetailView(word: word)
            }
            .fullScreenCover(isPresented: $showReview) {
                ReviewView()
            }
        }
    }
}

struct WordRow: View {
    let word: SavedWord

    private var firstMeaning: String {
        word.translation.components(separatedBy: "\n").first ?? word.translation
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(word.word)
                    .font(.headline)
                    .foregroundStyle(.primary)
                if let phonetic = word.phonetic {
                    Text(phonetic)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer(minLength: 6)
                if word.reviewCount > 0 {
                    Text("已复习 \(word.reviewCount)")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
            }
            Text(firstMeaning)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
        .padding(.vertical, 3)
    }
}

struct WordDetailView: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var store: ArticleStore
    let word: SavedWord

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    HStack(alignment: .firstTextBaseline, spacing: 10) {
                        Text(word.word)
                            .font(.largeTitle.bold())
                        Button {
                            SpeechService.shared.speak(word.word)
                        } label: {
                            Image(systemName: "speaker.wave.2.fill")
                                .font(.title3)
                                .foregroundStyle(.red)
                        }
                        .buttonStyle(.borderless)
                        if let phonetic = word.phonetic {
                            Text(phonetic)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                    }

                    ForEach(Array(word.translation.components(separatedBy: "\n").enumerated()), id: \.offset) { _, line in
                        Text(line)
                            .font(.body.weight(.semibold))
                            .foregroundStyle(.blue)
                    }

                    if !word.examples.isEmpty {
                        Divider()
                        Text("例句")
                            .font(.caption.weight(.bold))
                            .foregroundStyle(.secondary)
                            .textCase(.uppercase)
                        ForEach(Array(word.examples.enumerated()), id: \.offset) { _, example in
                            VStack(alignment: .leading, spacing: 3) {
                                Text(example.en)
                                    .font(.callout)
                                if let zh = example.zh {
                                    Text(zh)
                                        .font(.footnote)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }

                    if let article = store.article(for: word.sourceURL) {
                        Divider()
                        Text("来源文章")
                            .font(.caption.weight(.bold))
                            .foregroundStyle(.secondary)
                            .textCase(.uppercase)
                        NavigationLink(value: article) {
                            HStack(spacing: 10) {
                                Image(systemName: "newspaper")
                                    .foregroundStyle(.red)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(article.titleCN)
                                        .font(.callout)
                                        .foregroundStyle(.primary)
                                        .lineLimit(2)
                                        .multilineTextAlignment(.leading)
                                    Text(article.titleEN)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                        .lineLimit(1)
                                }
                                Spacer(minLength: 4)
                                Image(systemName: "chevron.right")
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(.tertiary)
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(20)
            }
            .navigationTitle("单词详情")
            .navigationBarTitleDisplayMode(.inline)
            .navigationDestination(for: Article.self) { article in
                ArticleDetailView(article: article, highlightWord: word.word)
            }
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(role: .destructive) {
                        store.removeWord(word.word)
                        dismiss()
                    } label: {
                        Image(systemName: "trash")
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("完成") { dismiss() }
                }
            }
        }
    }
}

struct ReviewView: View {
    @EnvironmentObject private var store: ArticleStore
    @Environment(\.dismiss) private var dismiss
    @State private var index = 0
    @State private var revealed = false

    private var words: [SavedWord] { store.savedWords }

    var body: some View {
        NavigationStack {
            VStack {
                if words.isEmpty {
                    ContentUnavailableView("没有可复习的单词", systemImage: "character.book.closed")
                } else {
                    let word = words[min(index, words.count - 1)]

                    Spacer()

                    VStack(spacing: 18) {
                        HStack(spacing: 12) {
                            Text(word.word)
                                .font(.system(size: 40, weight: .bold))
                                .multilineTextAlignment(.center)
                            Button {
                                SpeechService.shared.speak(word.word)
                            } label: {
                                Image(systemName: "speaker.wave.2.fill")
                                    .font(.title3)
                                    .foregroundStyle(.red)
                            }
                            .buttonStyle(.borderless)
                        }
                        if let phonetic = word.phonetic {
                            Text(phonetic)
                                .font(.title3)
                                .foregroundStyle(.secondary)
                        }

                        if revealed {
                            Divider().padding(.vertical, 4)
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(Array(word.translation.components(separatedBy: "\n").enumerated()), id: \.offset) { _, line in
                                    Text(line)
                                        .font(.body.weight(.semibold))
                                        .foregroundStyle(.blue)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                }
                                if let example = word.examples.first {
                                    Text(example.en)
                                        .font(.footnote)
                                        .italic()
                                        .foregroundStyle(.secondary)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .padding(.top, 4)
                                }
                            }
                        } else {
                            Text("点击查看释义")
                                .font(.subheadline)
                                .foregroundStyle(.tertiary)
                        }
                    }
                    .padding(28)
                    .frame(maxWidth: .infinity)
                    .background(Color(.secondarySystemGroupedBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 20))
                    .shadow(color: .black.opacity(0.06), radius: 10, y: 4)
                    .padding(.horizontal, 20)
                    .contentShape(Rectangle())
                    .onTapGesture { revealed.toggle() }

                    Spacer()

                    HStack(spacing: 16) {
                        Button {
                            goPrevious()
                        } label: {
                            Label("上一个", systemImage: "chevron.left")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.bordered)
                        .disabled(index == 0)

                        Button {
                            goNext()
                        } label: {
                            Label(index >= words.count - 1 ? "完成" : "下一个", systemImage: "chevron.right")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                    }
                    .padding(.horizontal, 20)
                    .padding(.bottom, 8)

                    Text("\(min(index + 1, words.count)) / \(words.count)")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .padding(.bottom, 12)
                }
            }
            .navigationTitle("复习")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("关闭") { dismiss() }
                }
            }
        }
    }

    private func goNext() {
        guard !words.isEmpty else { return }
        store.markReviewed(words[min(index, words.count - 1)].word)
        if index >= words.count - 1 {
            dismiss()
        } else {
            index += 1
            revealed = false
        }
    }

    private func goPrevious() {
        guard index > 0 else { return }
        index -= 1
        revealed = false
    }
}

struct ArticleRow: View {
    @EnvironmentObject private var store: ArticleStore
    let article: Article

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(article.titleCN)
                .font(.headline)
                .foregroundStyle(.primary)
                .lineLimit(3)
            Text(article.titleEN)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .lineLimit(3)
            HStack(spacing: 6) {
                Text(article.date)
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
                Text(article.tag == "ARCHIVE" ? "归档" : article.tag)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.tertiary)
                if store.isFavorite(article) {
                    Image(systemName: "bookmark.fill")
                        .foregroundStyle(.orange)
                        .font(.caption2)
                }
                Spacer()
            }
        }
        .padding(.vertical, 4)
    }
}
