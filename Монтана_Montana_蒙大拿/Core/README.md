# Montana Core

**One Core — All Platforms**

## Structure

```
Core/
├── Assets/
│   ├── AppIcon-1024.png    # Source icon (1024x1024)
│   └── AppIcon.icns        # macOS icon (generated)
├── Localization/           # Shared strings
└── Config/                 # Shared configuration
```

## Platforms

All platforms derive from Core:

| Platform | App | Icon Source |
|----------|-----|-------------|
| iOS | JunonaAI.app | Core/Assets/AppIcon-1024.png |
| macOS | Montana.app | Core/Assets/AppIcon.icns |
| Apple TV | Montana.app | Core/Assets/AppIcon-1024.png |

## Build Script

When building any platform, copy assets from Core:

```bash
# iOS
cp Core/Assets/AppIcon-1024.png iOS/Apps/JunonaAI/Assets.xcassets/AppIcon.appiconset/

# macOS
cp Core/Assets/AppIcon.icns macOS/Montana.app/Contents/Resources/

# Apple TV
cp Core/Assets/AppIcon-1024.png tvOS/Assets.xcassets/AppIcon.appiconset/
```

## Icon Regeneration

If AppIcon-1024.png changes, regenerate platform icons:

```bash
cd Core/Assets

# Generate macOS .icns
mkdir -p Montana.iconset
sips -z 16 16     AppIcon-1024.png --out Montana.iconset/icon_16x16.png
sips -z 32 32     AppIcon-1024.png --out Montana.iconset/icon_16x16@2x.png
sips -z 32 32     AppIcon-1024.png --out Montana.iconset/icon_32x32.png
sips -z 64 64     AppIcon-1024.png --out Montana.iconset/icon_32x32@2x.png
sips -z 128 128   AppIcon-1024.png --out Montana.iconset/icon_128x128.png
sips -z 256 256   AppIcon-1024.png --out Montana.iconset/icon_128x128@2x.png
sips -z 256 256   AppIcon-1024.png --out Montana.iconset/icon_256x256.png
sips -z 512 512   AppIcon-1024.png --out Montana.iconset/icon_256x256@2x.png
sips -z 512 512   AppIcon-1024.png --out Montana.iconset/icon_512x512.png
sips -z 1024 1024 AppIcon-1024.png --out Montana.iconset/icon_512x512@2x.png
iconutil -c icns Montana.iconset -o AppIcon.icns
rm -rf Montana.iconset
```

## Version

All platforms share the same version:
- **Version:** 1.5.0
- **Build:** 5
