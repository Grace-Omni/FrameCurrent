import AudioToolbox
import AVFoundation
import CoreGraphics
import Darwin
import Foundation

enum MergeError: Error, CustomStringConvertible {
    case message(String)

    var description: String {
        switch self {
        case .message(let value): return value
        }
    }
}

struct SourceSegment {
    let url: URL
    let asset: AVURLAsset
    let videoTrack: AVAssetTrack
    let audioTrack: AVAssetTrack?
    let sourceDuration: CMTime
    let duration: CMTime
    let displayRect: CGRect
    let preferredTransform: CGAffineTransform
    let nominalFrameRate: Float
}

struct TimelineSegment {
    let start: CMTime
    let duration: CMTime
    let transform: CGAffineTransform
}

enum SupportedOrientation: Equatable {
    case portrait
    case landscape

    var label: String {
        switch self {
        case .portrait: return "portrait 9:16"
        case .landscape: return "landscape 16:9"
        }
    }
}

func fail(_ message: String) throws -> Never {
    throw MergeError.message(message)
}

func finitePositive(_ value: CGFloat) -> Bool {
    value.isFinite && value > 0
}

func evenDimension(_ value: CGFloat) throws -> Int {
    guard finitePositive(value) else {
        throw MergeError.message("invalid source dimensions")
    }
    var rounded = Int(value.rounded())
    if !rounded.isMultiple(of: 2) { rounded -= 1 }
    guard rounded >= 2 else {
        throw MergeError.message("source dimensions are too small")
    }
    return rounded
}

func timeMinimum(_ first: CMTime, _ second: CMTime) -> CMTime {
    CMTimeCompare(first, second) <= 0 ? first : second
}

func shortToLongRatio(_ rect: CGRect) -> CGFloat {
    min(rect.width, rect.height) / max(rect.width, rect.height)
}

func supportedOrientation(for rect: CGRect) -> SupportedOrientation? {
    let targetRatio: CGFloat = 9.0 / 16.0
    guard abs(shortToLongRatio(rect) - targetRatio) <= 0.015 else {
        return nil
    }
    if rect.height > rect.width {
        return .portrait
    }
    if rect.width > rect.height {
        return .landscape
    }
    return nil
}

func normalizedH3Duration(
    sourceDuration: CMTime,
    nominalFrameRate: Float,
    index: Int,
    fileName: String
) throws -> CMTime {
    let sourceSeconds = sourceDuration.seconds
    let roundedSeconds = sourceSeconds.rounded()
    let frameRate = (nominalFrameRate.isFinite && nominalFrameRate > 0)
        ? Double(nominalFrameRate)
        : 24.0
    let extraSeconds = sourceSeconds - roundedSeconds
    let maximumExtraSeconds = 5.0 / frameRate + 0.006

    guard (5.0...15.0).contains(roundedSeconds),
          extraSeconds >= -0.01,
          extraSeconds <= maximumExtraSeconds else {
        try fail(
            "input \(index) duration \(String(format: "%.6f", sourceSeconds))s cannot be "
            + "normalized to a legal 5-15 second H3 clip: \(fileName)"
        )
    }

    let target = CMTime(seconds: roundedSeconds, preferredTimescale: 600)
    guard CMTimeCompare(sourceDuration, target) >= 0 else {
        try fail(
            "input \(index) is shorter than its normalized \(Int(roundedSeconds))s target: \(fileName)"
        )
    }
    return target
}

func fourCC(_ value: FourCharCode) -> String {
    let bytes: [UInt8] = [
        UInt8((value >> 24) & 0xff),
        UInt8((value >> 16) & 0xff),
        UInt8((value >> 8) & 0xff),
        UInt8(value & 0xff),
    ]
    return String(bytes: bytes.map { (32...126).contains($0) ? $0 : 46 }, encoding: .ascii) ?? "????"
}

func formatSubtype(of track: AVAssetTrack) -> FourCharCode? {
    guard let description = track.formatDescriptions.first else { return nil }
    return CMFormatDescriptionGetMediaSubType(description as! CMFormatDescription)
}

func loadSegment(url: URL, index: Int) throws -> SourceSegment {
    guard FileManager.default.fileExists(atPath: url.path) else {
        try fail("input \(index) does not exist: \(url.path)")
    }
    let asset = AVURLAsset(url: url)
    let videoTracks = asset.tracks(withMediaType: .video)
    guard videoTracks.count == 1, let videoTrack = videoTracks.first else {
        try fail("input \(index) must contain exactly one video track: \(url.lastPathComponent)")
    }
    let audioTracks = asset.tracks(withMediaType: .audio)
    guard audioTracks.count <= 1 else {
        try fail("input \(index) contains multiple audio tracks, which this H3 merger does not accept: \(url.lastPathComponent)")
    }

    let sourceDuration = videoTrack.timeRange.duration
    guard sourceDuration.isValid,
          sourceDuration.isNumeric,
          sourceDuration.seconds.isFinite,
          sourceDuration.seconds > 0 else {
        try fail("input \(index) has an invalid video duration: \(url.lastPathComponent)")
    }
    let naturalSize = videoTrack.naturalSize
    guard finitePositive(abs(naturalSize.width)), finitePositive(abs(naturalSize.height)) else {
        try fail("input \(index) has invalid encoded dimensions: \(url.lastPathComponent)")
    }
    let transformed = CGRect(origin: .zero, size: naturalSize)
        .applying(videoTrack.preferredTransform)
        .standardized
    guard finitePositive(transformed.width), finitePositive(transformed.height) else {
        try fail("input \(index) has an invalid display transform: \(url.lastPathComponent)")
    }

    let duration = try normalizedH3Duration(
        sourceDuration: sourceDuration,
        nominalFrameRate: videoTrack.nominalFrameRate,
        index: index,
        fileName: url.lastPathComponent
    )

    return SourceSegment(
        url: url,
        asset: asset,
        videoTrack: videoTrack,
        audioTrack: audioTracks.first,
        sourceDuration: sourceDuration,
        duration: duration,
        displayRect: transformed,
        preferredTransform: videoTrack.preferredTransform,
        nominalFrameRate: videoTrack.nominalFrameRate
    )
}

func normalizedTransform(for segment: SourceSegment, renderSize: CGSize) -> CGAffineTransform {
    // preferredTransform first rotates/translates encoded pixels into display
    // orientation. The next translation moves that oriented bounding box to
    // (0,0), followed by a uniform fit into the first clip's output canvas.
    let display = segment.displayRect
    let scale = min(renderSize.width / display.width, renderSize.height / display.height)
    let fittedWidth = display.width * scale
    let fittedHeight = display.height * scale
    let offsetX = (renderSize.width - fittedWidth) * 0.5
    let offsetY = (renderSize.height - fittedHeight) * 0.5

    return segment.preferredTransform
        .concatenating(CGAffineTransform(translationX: -display.minX, y: -display.minY))
        .concatenating(CGAffineTransform(scaleX: scale, y: scale))
        .concatenating(CGAffineTransform(translationX: offsetX, y: offsetY))
}

func atomicRename(from temporaryURL: URL, to finalURL: URL) throws {
    let result = temporaryURL.path.withCString { temporaryPath in
        finalURL.path.withCString { finalPath in
            Darwin.rename(temporaryPath, finalPath)
        }
    }
    guard result == 0 else {
        let description = String(cString: strerror(errno))
        throw MergeError.message("could not publish final movie atomically: \(description)")
    }
}

func validateOutput(
    _ url: URL,
    expectedDuration: CMTime,
    renderSize: CGSize,
    expectsAudio: Bool
) throws -> (duration: Double, videoCodec: String, audioCodec: String?) {
    let asset = AVURLAsset(url: url)
    let videoTracks = asset.tracks(withMediaType: .video)
    guard videoTracks.count == 1, let video = videoTracks.first else {
        try fail("export validation failed: expected exactly one video track")
    }
    let actualDuration = video.timeRange.duration.seconds
    let expectedSeconds = expectedDuration.seconds
    let tolerance = max(1.0 / 24.0, 0.002)
    guard actualDuration.isFinite, abs(actualDuration - expectedSeconds) <= tolerance else {
        try fail(
            "export validation failed: duration \(String(format: "%.6f", actualDuration))s, "
            + "expected \(String(format: "%.6f", expectedSeconds))s"
        )
    }

    let rect = CGRect(origin: .zero, size: video.naturalSize)
        .applying(video.preferredTransform)
        .standardized
    let dimensionTolerance: CGFloat = 1.0
    guard abs(rect.width - renderSize.width) <= dimensionTolerance,
          abs(rect.height - renderSize.height) <= dimensionTolerance else {
        try fail(
            "export validation failed: dimensions \(Int(rect.width.rounded()))x\(Int(rect.height.rounded())), "
            + "expected \(Int(renderSize.width))x\(Int(renderSize.height))"
        )
    }

    guard let videoSubtype = formatSubtype(of: video) else {
        try fail("export validation failed: video codec is unknown")
    }
    guard videoSubtype == kCMVideoCodecType_H264 else {
        try fail("export validation failed: expected H.264 video, got \(fourCC(videoSubtype))")
    }

    let audioTracks = asset.tracks(withMediaType: .audio)
    if expectsAudio && audioTracks.isEmpty {
        try fail("export validation failed: source audio was present but output audio is missing")
    }
    guard audioTracks.count <= 1 else {
        try fail("export validation failed: output contains multiple audio tracks")
    }
    var audioCodec: String?
    if let audio = audioTracks.first {
        guard let audioSubtype = formatSubtype(of: audio) else {
            try fail("export validation failed: audio codec is unknown")
        }
        let acceptedAAC: Set<FourCharCode> = [
            kAudioFormatMPEG4AAC,
            kAudioFormatMPEG4AAC_HE,
            kAudioFormatMPEG4AAC_HE_V2,
        ]
        guard acceptedAAC.contains(audioSubtype) else {
            try fail("export validation failed: expected AAC audio, got \(fourCC(audioSubtype))")
        }
        audioCodec = fourCC(audioSubtype)
    }
    return (actualDuration, fourCC(videoSubtype), audioCodec)
}

func merge(outputURL: URL, inputURLs: [URL]) throws {
    let normalizedOutputPath = outputURL.resolvingSymlinksInPath().standardizedFileURL.path
    guard outputURL.pathExtension.lowercased() == "mp4" else {
        try fail("output file must use the .mp4 extension")
    }
    for input in inputURLs {
        if input.resolvingSymlinksInPath().standardizedFileURL.path == normalizedOutputPath {
            try fail("output file must not overwrite an input clip")
        }
    }

    let segments = try inputURLs.enumerated().map { offset, url in
        try loadSegment(url: url, index: offset + 1)
    }
    guard let first = segments.first else {
        try fail("at least one input clip is required")
    }
    let sourceDurationTotal = segments.reduce(CMTime.zero) {
        CMTimeAdd($0, $1.sourceDuration)
    }

    guard let outputOrientation = supportedOrientation(for: first.displayRect) else {
        try fail(
            "first input must be portrait 9:16 or landscape 16:9; got "
            + "\(Int(first.displayRect.width.rounded()))x"
            + "\(Int(first.displayRect.height.rounded()))"
        )
    }
    let firstRatio = shortToLongRatio(first.displayRect)
    for (offset, segment) in segments.enumerated() {
        let ratio = shortToLongRatio(segment.displayRect)
        guard supportedOrientation(for: segment.displayRect) == outputOrientation,
              abs(ratio - firstRatio) <= 0.015 else {
            try fail(
                "input \(offset + 1) has an incompatible aspect ratio for "
                + "\(outputOrientation.label): "
                + "\(Int(segment.displayRect.width.rounded()))x\(Int(segment.displayRect.height.rounded()))"
            )
        }
    }

    let renderWidth = try evenDimension(first.displayRect.width)
    let renderHeight = try evenDimension(first.displayRect.height)
    let renderSize = CGSize(width: renderWidth, height: renderHeight)
    let renderRect = CGRect(origin: .zero, size: renderSize)
    guard supportedOrientation(for: renderRect) == outputOrientation else {
        try fail(
            "first input dimensions cannot produce a valid even-sized \(outputOrientation.label) canvas: "
            + "\(renderWidth)x\(renderHeight)"
        )
    }
    let composition = AVMutableComposition()
    guard let compositionVideo = composition.addMutableTrack(
        withMediaType: .video,
        preferredTrackID: kCMPersistentTrackID_Invalid
    ) else {
        try fail("could not create the destination video track")
    }
    let expectsAudio = segments.contains { $0.audioTrack != nil }
    let compositionAudio: AVMutableCompositionTrack?
    if expectsAudio {
        guard let track = composition.addMutableTrack(
            withMediaType: .audio,
            preferredTrackID: kCMPersistentTrackID_Invalid
        ) else {
            try fail("could not create the destination audio track")
        }
        compositionAudio = track
    } else {
        compositionAudio = nil
    }

    var cursor = CMTime.zero
    var audioEnd = CMTime.zero
    var timeline: [TimelineSegment] = []
    for (offset, segment) in segments.enumerated() {
        let videoRange = CMTimeRange(start: segment.videoTrack.timeRange.start, duration: segment.duration)
        do {
            try compositionVideo.insertTimeRange(videoRange, of: segment.videoTrack, at: cursor)
        } catch {
            try fail("could not append video from input \(offset + 1): \(error.localizedDescription)")
        }

        if let sourceAudio = segment.audioTrack {
            guard let compositionAudio else {
                try fail("internal error: destination audio track is unavailable")
            }
            if CMTimeCompare(audioEnd, cursor) < 0 {
                compositionAudio.insertEmptyTimeRange(
                    CMTimeRange(start: audioEnd, duration: CMTimeSubtract(cursor, audioEnd))
                )
                audioEnd = cursor
            }
            let audioDuration = timeMinimum(sourceAudio.timeRange.duration, segment.duration)
            if CMTimeCompare(audioDuration, .zero) > 0 {
                let audioRange = CMTimeRange(start: sourceAudio.timeRange.start, duration: audioDuration)
                do {
                    try compositionAudio.insertTimeRange(audioRange, of: sourceAudio, at: cursor)
                } catch {
                    try fail("could not append audio from input \(offset + 1): \(error.localizedDescription)")
                }
                audioEnd = CMTimeAdd(cursor, audioDuration)
            }
        }

        timeline.append(TimelineSegment(
            start: cursor,
            duration: segment.duration,
            transform: normalizedTransform(for: segment, renderSize: renderSize)
        ))
        cursor = CMTimeAdd(cursor, segment.duration)
    }

    let videoComposition = AVMutableVideoComposition()
    videoComposition.renderSize = renderSize
    let firstFPS = Int32(first.nominalFrameRate.rounded())
    let outputFPS: Int32 = (1...60).contains(firstFPS) ? firstFPS : 24
    videoComposition.frameDuration = CMTime(value: 1, timescale: outputFPS)
    videoComposition.instructions = timeline.map { segment in
        let instruction = AVMutableVideoCompositionInstruction()
        instruction.timeRange = CMTimeRange(start: segment.start, duration: segment.duration)
        instruction.enablePostProcessing = true
        let layer = AVMutableVideoCompositionLayerInstruction(assetTrack: compositionVideo)
        layer.setTransform(segment.transform, at: segment.start)
        instruction.layerInstructions = [layer]
        return instruction
    }

    let compatiblePresets = AVAssetExportSession.exportPresets(compatibleWith: composition)
    let preferredPresets = [AVAssetExportPresetHighestQuality, AVAssetExportPresetMediumQuality]
    guard let preset = preferredPresets.first(where: compatiblePresets.contains) else {
        try fail("no compatible H.264 export preset is available on this Mac")
    }
    guard let exporter = AVAssetExportSession(asset: composition, presetName: preset) else {
        try fail("could not create AVAssetExportSession")
    }
    guard exporter.supportedFileTypes.contains(.mp4) else {
        try fail("the selected export preset cannot write MP4")
    }

    try FileManager.default.createDirectory(
        at: outputURL.deletingLastPathComponent(),
        withIntermediateDirectories: true
    )
    let temporaryURL = outputURL.deletingLastPathComponent()
        .appendingPathComponent(".\(outputURL.deletingPathExtension().lastPathComponent)-\(UUID().uuidString).tmp.mp4")
    try? FileManager.default.removeItem(at: temporaryURL)
    var shouldRemoveTemporary = true
    defer {
        if shouldRemoveTemporary {
            try? FileManager.default.removeItem(at: temporaryURL)
        }
    }

    exporter.outputURL = temporaryURL
    exporter.outputFileType = .mp4
    exporter.videoComposition = videoComposition
    exporter.shouldOptimizeForNetworkUse = true
    exporter.timeRange = CMTimeRange(start: .zero, duration: cursor)

    let semaphore = DispatchSemaphore(value: 0)
    exporter.exportAsynchronously {
        semaphore.signal()
    }
    semaphore.wait()
    guard exporter.status == .completed else {
        let reason = exporter.error?.localizedDescription ?? "status \(exporter.status.rawValue)"
        try fail("MP4 export failed: \(reason)")
    }
    guard FileManager.default.fileExists(atPath: temporaryURL.path) else {
        try fail("MP4 export reported success but produced no file")
    }

    let validation = try validateOutput(
        temporaryURL,
        expectedDuration: cursor,
        renderSize: renderSize,
        expectsAudio: expectsAudio
    )
    try atomicRename(from: temporaryURL, to: outputURL)
    shouldRemoveTemporary = false

    let fileSize = (try FileManager.default.attributesOfItem(atPath: outputURL.path)[.size] as? NSNumber)?.uint64Value ?? 0
    let audioDescription = validation.audioCodec.map { "AAC(\($0))" } ?? "none"
    let normalizedAway = max(0.0, sourceDurationTotal.seconds - cursor.seconds)
    print(
        "created \(outputURL.path) | clips=\(segments.count) | "
        + "duration=\(String(format: "%.3f", validation.duration))s | "
        + "source_duration=\(String(format: "%.3f", sourceDurationTotal.seconds))s | "
        + "trimmed=\(String(format: "%.3f", normalizedAway))s | "
        + "dimensions=\(renderWidth)x\(renderHeight) | fps=\(outputFPS) | "
        + "video=H.264(\(validation.videoCodec)) | audio=\(audioDescription) | bytes=\(fileSize)"
    )
}

do {
    let arguments = CommandLine.arguments
    guard arguments.count >= 3 else {
        try fail("usage: merge_clips OUTPUT.mp4 INPUT1.mp4 [INPUT2.mp4 ...]")
    }
    let outputURL = URL(fileURLWithPath: arguments[1])
    let inputURLs = arguments.dropFirst(2).map { URL(fileURLWithPath: $0) }
    try merge(outputURL: outputURL, inputURLs: inputURLs)
} catch {
    FileHandle.standardError.write(Data("merge_clips: \(error)\n".utf8))
    exit(1)
}
