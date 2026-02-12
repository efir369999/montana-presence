import AVFoundation
import AppKit

class CameraManager: NSObject, ObservableObject {
    static let shared = CameraManager()

    @Published var isCameraRunning = false
    @Published var cameraError: String?

    private let captureSession = AVCaptureSession()
    private let sessionQueue = DispatchQueue(label: "network.montana.presence.camera")

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

            self.captureSession.commitConfiguration()
            self.captureSession.startRunning()

            DispatchQueue.main.async {
                self.isCameraRunning = true
                self.cameraError = nil
            }
        }
    }
}
