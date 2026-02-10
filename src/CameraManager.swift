import AVFoundation
import Vision
import AppKit

class CameraManager: NSObject, ObservableObject {
    static let shared = CameraManager()

    @Published var isCameraRunning = false
    @Published var faceDetected = false
    @Published var cameraError: String?

    private let captureSession = AVCaptureSession()
    private let sessionQueue = DispatchQueue(label: "network.montana.presence.camera")
    private let detectionInterval: TimeInterval = 3.0
    private var lastDetectionTime: UInt64 = 0
    private let lock = NSLock()

    private override init() {
        super.init()
    }

    func startCamera() {
        guard !isCameraRunning else { return }

        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            setupAndStart()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                DispatchQueue.main.async {
                    if granted {
                        self?.setupAndStart()
                    } else {
                        self?.cameraError = "Camera access denied"
                    }
                }
            }
        default:
            cameraError = "Camera access denied. Enable in System Settings > Privacy > Camera."
        }
    }

    func stopCamera() {
        sessionQueue.async { [weak self] in
            self?.captureSession.stopRunning()
        }
        DispatchQueue.main.async {
            self.isCameraRunning = false
            self.faceDetected = false
        }
    }

    private func setupAndStart() {
        sessionQueue.async { [weak self] in
            guard let self else { return }

            self.captureSession.beginConfiguration()
            self.captureSession.sessionPreset = .low

            guard let camera = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .unspecified),
                  let input = try? AVCaptureDeviceInput(device: camera) else {
                DispatchQueue.main.async {
                    self.cameraError = "No camera available"
                }
                return
            }

            if self.captureSession.canAddInput(input) {
                self.captureSession.addInput(input)
            }

            let output = AVCaptureVideoDataOutput()
            output.alwaysDiscardsLateVideoFrames = true
            output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
            output.setSampleBufferDelegate(self, queue: self.sessionQueue)

            if self.captureSession.canAddOutput(output) {
                self.captureSession.addOutput(output)
            }

            self.captureSession.commitConfiguration()
            self.captureSession.startRunning()

            DispatchQueue.main.async {
                self.isCameraRunning = true
                self.cameraError = nil
            }
        }
    }

    private func detectFace(in pixelBuffer: CVPixelBuffer) {
        let request = VNDetectFaceRectanglesRequest()
        let handler = VNImageRequestHandler(cvPixelBuffer: pixelBuffer, options: [:])

        do {
            try handler.perform([request])
            let hasFace = (request.results ?? []).isEmpty == false
            DispatchQueue.main.async { [weak self] in
                self?.faceDetected = hasFace
                Task { @MainActor in
                    PresenceEngine.shared.faceDetectionResult(hasFace)
                }
            }
        } catch {
            // Vision error — skip this frame
        }
    }
}

extension CameraManager: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        let nowTicks = DispatchTime.now().uptimeNanoseconds
        lock.lock()
        let elapsed = Double(nowTicks - lastDetectionTime) / 1_000_000_000
        if elapsed < detectionInterval {
            lock.unlock()
            return
        }
        lastDetectionTime = nowTicks
        lock.unlock()

        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        detectFace(in: pixelBuffer)
    }
}
