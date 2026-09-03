import AppKit
import CoreGraphics
import Foundation

enum SimilarityError: Error, CustomStringConvertible {
    case message(String)

    var description: String {
        switch self {
        case .message(let value): return value
        }
    }
}

func loadImage(_ path: String) throws -> CGImage {
    let url = URL(fileURLWithPath: path)
    guard let image = NSImage(contentsOf: url) else {
        throw SimilarityError.message("could not open image: \(path)")
    }
    var proposedRect = CGRect(origin: .zero, size: image.size)
    guard let cgImage = image.cgImage(forProposedRect: &proposedRect, context: nil, hints: nil) else {
        throw SimilarityError.message("could not decode image: \(path)")
    }
    return cgImage
}

func normalizedPixels(_ image: CGImage, width: Int = 96, height: Int = 96) throws -> [UInt8] {
    var bytes = [UInt8](repeating: 0, count: width * height * 4)
    let created = bytes.withUnsafeMutableBytes { rawBuffer -> Bool in
        guard let address = rawBuffer.baseAddress,
              let context = CGContext(
                data: address,
                width: width,
                height: height,
                bitsPerComponent: 8,
                bytesPerRow: width * 4,
                space: CGColorSpaceCreateDeviceRGB(),
                bitmapInfo: CGBitmapInfo.byteOrder32Big.rawValue
                    | CGImageAlphaInfo.premultipliedLast.rawValue
              ) else {
            return false
        }
        context.interpolationQuality = .high
        context.setFillColor(CGColor(red: 0, green: 0, blue: 0, alpha: 1))
        context.fill(CGRect(x: 0, y: 0, width: width, height: height))
        context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
        return true
    }
    guard created else {
        throw SimilarityError.message("could not create comparison bitmap")
    }
    return bytes
}

func similarity(_ first: [UInt8], _ second: [UInt8]) throws -> Double {
    guard first.count == second.count, first.count.isMultiple(of: 4) else {
        throw SimilarityError.message("normalized image buffers are incompatible")
    }

    // Mean absolute RGB error is easy to explain and deterministic. A value of
    // 1.0 is pixel-identical; 0.0 is maximally different. Alpha is ignored
    // because JPEG inputs are opaque and the metric should reflect appearance.
    var difference: UInt64 = 0
    var channelCount: UInt64 = 0
    for pixelOffset in stride(from: 0, to: first.count, by: 4) {
        for channel in 0..<3 {
            difference += UInt64(abs(Int(first[pixelOffset + channel]) - Int(second[pixelOffset + channel])))
            channelCount += 1
        }
    }
    let maximumDifference = Double(channelCount) * 255.0
    let score = 1.0 - Double(difference) / maximumDifference
    return min(1.0, max(0.0, score))
}

do {
    let arguments = CommandLine.arguments
    guard arguments.count == 3 else {
        throw SimilarityError.message("usage: image_similarity FIRST_IMAGE SECOND_IMAGE")
    }
    let first = try normalizedPixels(loadImage(arguments[1]))
    let second = try normalizedPixels(loadImage(arguments[2]))
    let score = try similarity(first, second)
    print(String(format: "%.6f", score))
} catch {
    FileHandle.standardError.write(Data("image_similarity: \(error)\n".utf8))
    exit(1)
}
