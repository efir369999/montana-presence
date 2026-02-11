// swift-tools-version: 5.9
// MontanaCore — общее ядро для всех 3 приложений Montana

import PackageDescription

let package = Package(
    name: "MontanaCore",
    platforms: [
        .iOS(.v17),
        .macOS(.v14)
    ],
    products: [
        .library(
            name: "MontanaCore",
            targets: ["MontanaCore"]
        ),
    ],
    targets: [
        .target(
            name: "MontanaCore",
            dependencies: [],
            path: "Sources/MontanaCore"
        ),
        .testTarget(
            name: "MontanaCoreTests",
            dependencies: ["MontanaCore"],
            path: "Tests/MontanaCoreTests"
        ),
    ]
)
