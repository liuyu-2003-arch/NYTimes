import SwiftUI

@main
struct NYTimesReaderApp: App {
    @StateObject private var store = ArticleStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
        }
    }
}
