from pathlib import Path
import re

p = Path('android/love/src/main/java/org/love2d/android/GameActivity.java')
if not p.exists():
    raise SystemExit(f'Missing launcher source: {p}. The love-android 11.5a wrapper was not prepared.')
s = p.read_text(encoding='utf-8')

for old, new in [
    ('import java.util.ArrayList;\nimport java.util.HashMap;', 'import java.util.ArrayList;\nimport java.util.HashMap;\nimport java.util.Collections;\nimport java.util.LinkedHashSet;\nimport java.util.Set;'),
    ('import android.os.Environment;\n', 'import android.os.Environment;\nimport android.provider.Settings;\n'),
]:
    if new not in s:
        if old not in s:
            raise SystemExit(f'Expected import block not found: {old!r}')
        s = s.replace(old, new, 1)

new_method = r'''    private static final int LOVEGAME_MAX_DEPTH = 6;
    private static final int LOVEGAME_MAX_RESULTS = 32;
    private static final Object lovegameSelectionLock = new Object();

    private ArrayList<String> findLovegameFolders(File root) {
        ArrayList<String> results = new ArrayList<String>();
        if (root == null || !root.isDirectory()) return results;

        ArrayList<File> queue = new ArrayList<File>();
        ArrayList<Integer> depths = new ArrayList<Integer>();
        Set<String> visited = new LinkedHashSet<String>();
        queue.add(root);
        depths.add(0);

        for (int index = 0; index < queue.size() && results.size() < LOVEGAME_MAX_RESULTS; index++) {
            File dir = queue.get(index);
            int depth = depths.get(index);
            try {
                String canonical = dir.getCanonicalPath();
                if (!visited.add(canonical)) continue;
            } catch (IOException ignored) {
                if (!visited.add(dir.getAbsolutePath())) continue;
            }

            if (dir.getName().equalsIgnoreCase("lovegame")) {
                File main = new File(dir, "main.lua");
                if (main.isFile() && main.canRead()) {
                    results.add(dir.getAbsolutePath() + File.separator);
                    continue;
                }
            }

            if (depth >= LOVEGAME_MAX_DEPTH) continue;
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

    private String chooseLovegameFolder(final ArrayList<String> folders) {
        if (folders.size() == 1) return folders.get(0);

        final android.content.SharedPreferences prefs = getSharedPreferences("lovegame", Context.MODE_PRIVATE);
        final String last = prefs.getString("last_path", "");
        if (last.length() > 0 && folders.contains(last)) return last;

        final String[] labels = new String[folders.size()];
        for (int i = 0; i < folders.size(); i++) labels[i] = folders.get(i);
        final String[] selected = new String[] { null };

        synchronized (lovegameSelectionLock) {
            runOnUiThread(new Runnable() {
                @Override public void run() {
                    AlertDialog dialog = new AlertDialog.Builder(GameActivity.this)
                        .setTitle("Choose LÖVE game")
                        .setItems(labels, new DialogInterface.OnClickListener() {
                            @Override public void onClick(DialogInterface dialog, int which) {
                                synchronized (lovegameSelectionLock) {
                                    selected[0] = folders.get(which);
                                    lovegameSelectionLock.notifyAll();
                                }
                            }
                        })
                        .setOnCancelListener(new DialogInterface.OnCancelListener() {
                            @Override public void onCancel(DialogInterface dialog) {
                                synchronized (lovegameSelectionLock) {
                                    selected[0] = "";
                                    lovegameSelectionLock.notifyAll();
                                }
                            }
                        })
                        .create();
                    dialog.setCanceledOnTouchOutside(false);
                    dialog.show();
                }
            });
            try {
                while (selected[0] == null) lovegameSelectionLock.wait();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }

        if (selected[0] != null && selected[0].length() > 0) {
            prefs.edit().putString("last_path", selected[0]).apply();
            return selected[0];
        }
        return "";
    }

    private boolean hasAllFilesAccess() {
        return android.os.Build.VERSION.SDK_INT < 30 || Environment.isExternalStorageManager();
    }

    private void requestAllFilesAccessIfNeeded() {
        if (android.os.Build.VERSION.SDK_INT < 30 || hasAllFilesAccess()) return;
        try {
            Intent intent = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION);
            intent.setData(Uri.parse("package:" + getPackageName()));
            startActivity(intent);
        } catch (Exception e) {
            Log.e("GameActivity", "Unable to open all-files access settings", e);
        }
    }

    protected void checkLovegameFolder() {
        if (embed) return;

        Log.d("GameActivity", "Searching shared storage recursively for lovegame/main.lua");

        // Keep the original app-specific fallback first. It works without broad storage access.
        File appGames = getExternalFilesDir("games");
        if (appGames != null) {
            File localLovegame = new File(appGames, "lovegame/main.lua");
            if (localLovegame.isFile()) {
                gamePath = localLovegame.getParentFile().getAbsolutePath() + File.separator;
                storagePermissionUnnecessary = true;
                return;
            }
        }

        // Android 11+ blocks unrestricted recursive path traversal under scoped storage.
        // Request the special All files access only for this launcher feature.
        if (android.os.Build.VERSION.SDK_INT >= 30 && !hasAllFilesAccess()) {
            requestAllFilesAccessIfNeeded();
            return;
        }

        if (!hasAllFilesAccess() && android.os.Build.VERSION.SDK_INT >= 29) return;

        ArrayList<String> candidates = new ArrayList<String>();
        candidates.addAll(findLovegameFolders(Environment.getExternalStorageDirectory()));

        if (candidates.size() == 0) {
            Log.d("GameActivity", "No shared-storage lovegame folder found");
            return;
        }

        String selected = chooseLovegameFolder(candidates);
        if (selected.length() > 0) {
            gamePath = selected;
            storagePermissionUnnecessary = false;
            Log.d("GameActivity", "Selected lovegame directory: " + gamePath);
        }
    }
'''

pattern = re.compile(r'    protected void checkLovegameFolder\(\) \{.*?^    \}\n(?=\s*@Override\n\s*protected void onDestroy)', re.S | re.M)
if not pattern.search(s):
    raise SystemExit('Expected checkLovegameFolder method was not found; refusing unsafe edit.')
s = pattern.sub(new_method + '\n', s, count=1)
p.write_text(s, encoding='utf-8')

manifest = Path('android/love/src/main/AndroidManifest.xml')
if not manifest.exists():
    raise SystemExit(f'Missing manifest: {manifest}')
ms = manifest.read_text(encoding='utf-8')
perm = '  <uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" />'
if 'android.permission.MANAGE_EXTERNAL_STORAGE' not in ms:
    ms = ms.replace('  <uses-permission android:name="android.permission.INTERNET" />', '  <uses-permission android:name="android.permission.INTERNET" />\n' + perm, 1)
manifest.write_text(ms, encoding='utf-8')

print('lovegame launcher patch applied successfully')
