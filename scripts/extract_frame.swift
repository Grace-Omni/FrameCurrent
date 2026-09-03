import AppKit
import AVFoundation
import Foundation

enum FrameToolError: Error, CustomStringConvertible {
    case message(String)

    var description: String {
        switch self {
        case .message(let value): return value
        }
    }
}

func extract(videoPath: String, outputPath: String, position: String) throws {
    guard position == "first" || position == "last" else {
        throw FrameToolError.message("position must be 'first' or 'last'")
    }
    let videoURL = URL(fileURLWithPath: videoPath)
    guard FileManager.default.fileExists(atPath: videoURL.path) else {
        throw FrameToolError.message("input video does not exist: \(videoURL.path)")
    }

    let asset = AVURLAsset(url: videoURL)
    let duration = asset.duration
    guard duration.isValid, duration.seconds.isFinite, duration.seconds > 0 else {
        throw FrameToolError.message("input video has no valid duration")
    }

    let generator = AVAssetImageGenerator(asset: asset)
    generator.appliesPreferredTrackTransform = true
    generator.requestedTimeToleranceBefore = .zero
    generator.requestedTimeToleranceAfter = .zero

    let frameStep = CMTime(value: 1, timescale: 24)
    let requestedTime: CMTime
    if position == "first" {
        requestedTime = .zero
    } else {
        let candidate = CMTimeSubtract(duration, frameStep)
        requestedTime = CMTimeCompare(candidate, .zero) > 0 ? candidate : .zero
    }

    var actualTime = CMTime.invalid
    let image = try generator.copyCGImage(at: requestedTime, actualTime: &actualTime)
    let bitmap = NSBitmapImageRep(cgImage: image)
    guard let jpeg = bitmap.representation(
        using: .jpeg,
        properties: [.compressionFactor: NSNumber(value: 0.94)]
    ) else {
        throw FrameToolError.message("could not encode JPEG")
    }

    let outputURL = URL(fileURLWithPath: outputPath)
    try FileManager.default.createDirectory(
        at: outputURL.deletingLastPathComponent(),
        withIntermediateDirectories: true
    )
    try jpeg.write(to: outputURL, options: .atomic)
    print("extracted \(position) frame at \(String(format: "%.6f", actualTime.seconds))s -> \(outputURL.path)")
}

do {
    let arguments = CommandLine.arguments
    guard arguments.count == 4 else {
        throw FrameToolError.message("usage: extract_frame INPUT.mp4 OUTPUT.jpg first|last")
    }
    try extract(videoPath: arguments[1], outputPath: arguments[2], position: arguments[3])
} catch {
    FileHandle.standardError.write(Data("extract_frame: \(error)\n".utf8))
    exit(1)
}
