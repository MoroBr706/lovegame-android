# LÖVE 11.5 lovegame Android build

This repository contains the supplied LÖVE 11.5 source plus a GitHub Actions build that obtains the official `love-android` 11.5a Android wrapper at build time. The wrapper is kept separate because the supplied archive is the generic LÖVE source tree and does not contain the Android Gradle project.

The workflow then patches `GameActivity.java` so the normal (non-embedded) Android launcher:

- keeps the existing `.love` / `file://` / `content://` loading behavior;
- keeps the original app-specific `Android/data/.../games/lovegame` fallback;
- on Android 11+ requests the system **All files access** special permission only when the shared-storage `lovegame` scanner is needed;
- searches `/storage/emulated/0` recursively with a maximum depth of 6;
- accepts only directories named `lovegame` containing a readable `main.lua`;
- supports multiple matches and lets the user choose one;
- remembers the last selected path;
- does not silently exit when no external game is found.

Android's official documentation says `MANAGE_EXTERNAL_STORAGE` is the mechanism for broad shared-storage access and that the app must send the user to the system special-access page; this is why the APK cannot silently grant itself this access.
