from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
GAME_ACTIVITY = ROOT / "android/love/src/main/java/org/love2d/android/GameActivity.java"
MANIFEST = ROOT / "android/love/src/main/AndroidManifest.xml"


def fail(msg):
    raise SystemExit("ERROR: " + msg)


def add_import(source, import_line, anchor):
    if import_line in source:
        return source
    if anchor not in source:
        fail(f"Expected import anchor not found: {anchor}")
    return source.replace(anchor, anchor + "\n" + import_line, 1)


def replace_method(source, signature, replacement):
    start = source.find(signature)
    if start < 0:
        fail(f"Expected method not found: {signature}")
    brace = source.find("{", start)
    if brace < 0:
        fail(f"Opening brace not found for: {signature}")
    depth = 0
    in_string = False
    in_char = False
    escaped = False
    line_comment = False
    block_comment = False
    i = brace
    while i < len(source):
        c = source[i]
        n = source[i + 1] if i + 1 < len(source) else ""
        if line_comment:
            if c == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if c == "*" and n == "/":
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if in_string:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
            i += 1
            continue
        if in_char:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == "'":
                in_char = False
            i += 1
            continue
        if c == "/" and n == "/":
            line_comment = True
            i += 2
            continue
        if c == "/" and n == "*":
            block_comment = True
            i += 2
            continue
        if c == '"':
            in_string = True
            i += 1
            continue
        if c == "'":
            in_char = True
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return source[:start] + replacement + source[i + 1:]
        i += 1
    fail(f"Closing brace not found for: {signature}")


CHECK_METHOD = r'''    protected void checkLovegameFolder() {
        if (embed) return;

        Log.d("GameActivity", "Searching shared storage for lovegame/main.lua");

        File ext = getExternalFilesDir("games");
        if (ext != null) {
            File appGame = new File(ext, "lovegame/main.lua");
            if (appGame.isFile() && appGame.canRead()) {
                applyLoveGameOrientation(appGame.getParentFile().getAbsolutePath());
                gamePath = appGame.getParentFile().getAbsolutePath() + File.separator;
                storagePermissionUnnecessary = true;
                return;
            }
        }

        if (android.os.Build.VERSION.SDK_INT >= 30 && !Environment.isExternalStorageManager()) {
            requestAllFilesAccess();
            return;
        }

        if (android.os.Build.VERSION.SDK_INT < 30 && !hasExternalStoragePermission()) {
            return;
        }

        ArrayList<String> matches = findLovegameFolders(Environment.getExternalStorageDirectory());
        if (matches.isEmpty()) {
            showNoLovegameDialog();
            return;
        }

        String last = getSharedPreferences("lovegame_launcher", Context.MODE_PRIVATE)
                .getString("last_path", "");

        if (!last.isEmpty()) {
            File lastMain = new File(last, "main.lua");
            if (lastMain.isFile() && lastMain.canRead()) {
                applyLoveGameOrientation(lastMain.getParentFile().getAbsolutePath());
                gamePath = lastMain.getParentFile().getAbsolutePath() + File.separator;
                storagePermissionUnnecessary = false;
                return;
            }
        }

        if (matches.size() == 1) {
            selectLovegameFolder(matches.get(0));
        } else {
            chooseLovegameFolder(matches);
        }
    }

    private ArrayList<String> findLovegameFolders(File root) {
        final int MAX_DEPTH = 6;
        final int MAX_RESULTS = 32;
        ArrayList<String> results = new ArrayList<String>();
        ArrayList<File> queue = new ArrayList<File>();
        ArrayList<Integer> depths = new ArrayList<Integer>();
        Set<String> visited = new LinkedHashSet<String>();

        if (root == null || !root.isDirectory()) return results;

        queue.add(root);
        depths.add(0);

        for (int i = 0; i < queue.size() && results.size() < MAX_RESULTS; i++) {
            File dir = queue.get(i);
            int depth = depths.get(i);
            String canonical;
            try {
                canonical = dir.getCanonicalPath();
            } catch (IOException e) {
                canonical = dir.getAbsolutePath();
            }
            if (!visited.add(canonical)) continue;

            if (dir.getName().equalsIgnoreCase("lovegame")) {
                File main = new File(dir, "main.lua");
                if (main.isFile() && main.canRead()) {
                    results.add(dir.getAbsolutePath() + File.separator);
                    continue;
                }
            }

            if (depth >= MAX_DEPTH) continue;
            File[] children = dir.listFiles();
            if (children == null) continue;

            for (File child : children) {
                if (!child.isDirectory()) continue;
                String name = child.getName();
                if (name.equals("Android") || name.equals(".android") || name.startsWith(".")) continue;
                queue.add(child);
                depths.add(depth + 1);
            }
        }

        Collections.sort(results);
        return results;
    }

    private void applyLoveGameOrientation(final String folder) {
        // LÖVE determines Android orientation from the game's configured
        // window aspect ratio (conf.lua width/height). Apply the same choice
        // before native LÖVE continues so a landscape project does not start
        // inside a portrait Activity and get cropped until the user rotates.
        int width = 800;
        int height = 600;
        File conf = new File(folder, "conf.lua");

        if (conf.isFile() && conf.canRead()) {
            StringBuilder text = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(new FileReader(conf))) {
                String line;
                int chars = 0;
                while ((line = reader.readLine()) != null && chars < 262144) {
                    text.append(line).append('\n');
                    chars += line.length() + 1;
                }
            } catch (Exception e) {
                Log.w("GameActivity", "Unable to read conf.lua for orientation", e);
            }

            java.util.regex.Matcher wm = java.util.regex.Pattern
                    .compile("t\\s*\\.\\s*window\\s*\\.\\s*width\\s*=\\s*(\\d+)")
                    .matcher(text.toString());
            java.util.regex.Matcher hm = java.util.regex.Pattern
                    .compile("t\\s*\\.\\s*window\\s*\\.\\s*height\\s*=\\s*(\\d+)")
                    .matcher(text.toString());
            if (wm.find()) {
                try { width = Integer.parseInt(wm.group(1)); } catch (NumberFormatException ignored) {}
            }
            if (hm.find()) {
                try { height = Integer.parseInt(hm.group(1)); } catch (NumberFormatException ignored) {}
            }
        }

        final int requested;
        if (width > height) {
            requested = ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE;
        } else if (height > width) {
            requested = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT;
        } else {
            requested = ActivityInfo.SCREEN_ORIENTATION_FULL_SENSOR;
        }

        Log.d("GameActivity", "LoveGame orientation from conf.lua: "
                + width + "x" + height + " -> " + requested);

        runOnUiThread(new Runnable() {
            @Override public void run() {
                try {
                    setRequestedOrientation(requested);
                } catch (Exception e) {
                    Log.w("GameActivity", "Unable to apply LoveGame orientation", e);
                }
            }
        });
    }

    private void selectLovegameFolder(String folder) {
        File dir = new File(folder);
        File main = new File(dir, "main.lua");
        if (!dir.isDirectory() || !main.isFile() || !main.canRead()) return;

        applyLoveGameOrientation(dir.getAbsolutePath());
        gamePath = dir.getAbsolutePath() + File.separator;
        storagePermissionUnnecessary = false;
        getSharedPreferences("lovegame_launcher", Context.MODE_PRIVATE)
                .edit().putString("last_path", dir.getAbsolutePath()).apply();

        Log.d("GameActivity", "Selected lovegame: " + gamePath);
    }

    private void chooseLovegameFolder(final ArrayList<String> matches) {
        final Object lock = new Object();
        final String[] selected = new String[] { null };

        runOnUiThread(new Runnable() {
            @Override public void run() {
                String[] labels = new String[matches.size()];
                for (int i = 0; i < matches.size(); i++) labels[i] = matches.get(i);

                new AlertDialog.Builder(GameActivity.this)
                        .setTitle("Escolha o LoveGame")
                        .setItems(labels, new DialogInterface.OnClickListener() {
                            @Override public void onClick(DialogInterface dialog, int which) {
                                synchronized (lock) {
                                    selected[0] = matches.get(which);
                                    lock.notifyAll();
                                }
                            }
                        })
                        .setOnCancelListener(new DialogInterface.OnCancelListener() {
                            @Override public void onCancel(DialogInterface dialog) {
                                synchronized (lock) {
                                    selected[0] = "";
                                    lock.notifyAll();
                                }
                            }
                        })
                        .setCancelable(true)
                        .show();
            }
        });

        synchronized (lock) {
            while (selected[0] == null) {
                try {
                    lock.wait();
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return;
                }
            }
        }

        if (!selected[0].isEmpty()) {
            selectLovegameFolder(selected[0]);
        }
    }

    private void showNoLovegameDialog() {
        runOnUiThread(new Runnable() {
            @Override public void run() {
                new AlertDialog.Builder(GameActivity.this)
                        .setTitle("LoveGame não encontrado")
                        .setMessage("Não foi encontrada nenhuma pasta lovegame contendo main.lua no armazenamento compartilhado.")
                        .setPositiveButton("OK", null)
                        .show();
            }
        });
    }

    private void requestAllFilesAccess() {
        if (android.os.Build.VERSION.SDK_INT < 30 || Environment.isExternalStorageManager()) return;
        waitingForAllFilesAccess = true;
        runOnUiThread(new Runnable() {
            @Override public void run() {
                try {
                    Intent intent = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION);
                    intent.setData(Uri.parse("package:" + getPackageName()));
                    startActivity(intent);
                } catch (Exception e) {
                    Log.e("GameActivity", "Unable to open all-files access settings", e);
                    try {
                        startActivity(new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION));
                    } catch (Exception ignored) {
                        showExternalStoragePermissionMissingDialog();
                    }
                }
            }
        });
    }

'''

ON_RESUME = r'''    @Override
    public void onResume() {
        super.onResume();

        // Android 11+ grants all-files access from Settings. The first launch
        // must finish locating the game and applying its orientation BEFORE
        // native LÖVE is restarted. Starting native immediately after
        // setRequestedOrientation() races Android's configuration change and
        // can leave a landscape game rendered inside a portrait surface.
        if (android.os.Build.VERSION.SDK_INT >= 30
                && waitingForAllFilesAccess
                && Environment.isExternalStorageManager()
                && gamePath.length() == 0) {
            waitingForAllFilesAccess = false;

            new Thread(new Runnable() {
                @Override public void run() {
                    Log.d("GameActivity", "All-files access granted; locating LoveGame before native restart.");

                    // This performs the recursive scan off the UI thread.
                    // checkLovegameFolder() also selects the remembered/single
                    // folder and schedules the orientation change on the UI thread.
                    checkLovegameFolder();

                    if (gamePath.length() == 0) {
                        Log.w("GameActivity", "LoveGame was not selected after storage permission.");
                        return;
                    }

                    runOnUiThread(new Runnable() {
                        @Override public void run() {
                            // Give Android a chance to commit the requested
                            // orientation before SDL creates its native window.
                            getWindow().getDecorView().postDelayed(new Runnable() {
                                @Override public void run() {
                                    if (gamePath.length() == 0) return;
                                    Log.d("GameActivity", "Starting native LÖVE after orientation setup.");
                                    resetNative();
                                    startNative();
                                }
                            }, 500);
                        }
                    });
                }
            }, "LoveGamePermissionLoad").start();
        }
    }
'''

HAS_PERMISSION = r'''    @Keep
    public boolean hasExternalStoragePermission() {
        if (android.os.Build.VERSION.SDK_INT >= 30) {
            return Environment.isExternalStorageManager();
        }

        if (ActivityCompat.checkSelfPermission(this,
                Manifest.permission.READ_EXTERNAL_STORAGE)
                == PackageManager.PERMISSION_GRANTED) {
            return true;
        }

        Log.d("GameActivity", "Requesting permission and locking LÖVE thread until we have an answer.");
        ActivityCompat.requestPermissions(this,
                new String[]{Manifest.permission.READ_EXTERNAL_STORAGE},
                EXTERNAL_STORAGE_REQUEST_CODE);
        synchronized (externalStorageRequestDummy) {
            try {
                externalStorageRequestDummy.wait();
            } catch (InterruptedException e) {
                Log.d("GameActivity", "requesting external storage permission", e);
                Thread.currentThread().interrupt();
                return false;
            }
        }

        return ActivityCompat.checkSelfPermission(this,
                Manifest.permission.READ_EXTERNAL_STORAGE)
                == PackageManager.PERMISSION_GRANTED;
    }
'''


def main():
    if not GAME_ACTIVITY.exists():
        fail(f"Missing launcher source: {GAME_ACTIVITY}. The workflow must clone love-android 11.5a before running this patch.")
    if not MANIFEST.exists():
        fail(f"Missing manifest: {MANIFEST}")

    source = GAME_ACTIVITY.read_text(encoding="utf-8")
    backup = GAME_ACTIVITY.with_suffix(".java.lovegame-original")
    if not backup.exists():
        shutil.copy2(GAME_ACTIVITY, backup)

    source = add_import(source, "import java.util.Collections;", "import java.util.ArrayList;")
    source = add_import(source, "import java.util.LinkedHashSet;", "import java.util.Collections;")
    source = add_import(source, "import java.util.Set;", "import java.util.LinkedHashSet;")
    source = add_import(source, "import android.provider.Settings;", "import android.os.Environment;")
    source = add_import(source, "import android.content.pm.ActivityInfo;", "import android.content.pm.PackageManager;")
    source = add_import(source, "import java.io.BufferedReader;", "import java.io.File;")
    source = add_import(source, "import java.io.FileReader;", "import java.io.BufferedReader;")

    fields = '''    private static final int LOVEGAME_MAX_DEPTH = 6;\n    private static final int LOVEGAME_MAX_RESULTS = 32;\n    private boolean waitingForAllFilesAccess = false;\n'''
    marker = "    private boolean shortEdgesMode = false;"
    if "LOVEGAME_MAX_DEPTH" not in source:
        if marker not in source:
            fail("Could not find shortEdgesMode field")
        source = source.replace(marker, marker + "\n" + fields, 1)

    source = replace_method(source, "    protected void checkLovegameFolder()", CHECK_METHOD)
    source = replace_method(source, "    @Override\n    public void onResume()", ON_RESUME)
    source = replace_method(source, "    @Keep\n    public boolean hasExternalStoragePermission()", HAS_PERMISSION)
    GAME_ACTIVITY.write_text(source, encoding="utf-8")

    ms = MANIFEST.read_text(encoding="utf-8")
    permission = '<uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" />'
    if "android.permission.MANAGE_EXTERNAL_STORAGE" not in ms:
        m = re.search(r"<manifest\b[^>]*>", ms)
        if not m:
            fail("Could not find <manifest> in AndroidManifest.xml")
        ms = ms[:m.end()] + "\n    " + permission + ms[m.end():]
        MANIFEST.write_text(ms, encoding="utf-8")

    print("LoveGame launcher patch applied successfully")


if __name__ == "__main__":
    main()
