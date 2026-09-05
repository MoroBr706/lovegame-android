#!/usr/bin/env python3

from pathlib import Path
import re
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]

GAME_ACTIVITY = (
    ROOT
    / "android"
    / "love"
    / "src"
    / "main"
    / "java"
    / "org"
    / "love2d"
    / "android"
    / "GameActivity.java"
)

MANIFEST = (
    ROOT
    / "android"
    / "love"
    / "src"
    / "main"
    / "AndroidManifest.xml"
)


def fail(message):
    print("")
    print("ERRO:", message)
    print("")
    sys.exit(1)


def replace_method(source, signature, replacement):
    """
    Substitui um método Java inteiro encontrando a assinatura
    e fazendo o balanceamento real das chaves.
    """

    start = source.find(signature)

    if start == -1:
        fail(
            "Não encontrei o método esperado:\n"
            + signature
        )

    brace_start = source.find("{", start)

    if brace_start == -1:
        fail(
            "Encontrei a assinatura, mas não encontrei "
            "a chave inicial do método:\n"
            + signature
        )

    depth = 0
    in_string = False
    in_char = False
    escaped = False
    line_comment = False
    block_comment = False

    end = None
    i = brace_start

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
                end = i + 1
                break

        i += 1

    if end is None:
        fail(
            "Não consegui encontrar o fim do método:\n"
            + signature
        )

    return source[:start] + replacement + source[end:]


def add_import(source, import_line):
    if import_line in source:
        return source

    marker = "import android.Manifest;"

    if marker not in source:
        fail(
            "Não encontrei o ponto esperado para adicionar o import:\n"
            + marker
        )

    return source.replace(
        marker,
        marker + "\n" + import_line,
        1
    )


def add_java_imports(source):
    imports = [
        "import android.provider.Settings;",
        "import java.util.ArrayDeque;",
        "import java.util.Collections;",
        "import java.util.Deque;",
        "import java.util.LinkedHashSet;",
        "import java.util.Set;",
    ]

    for item in imports:
        source = add_import(source, item)

    return source


def add_fields(source):
    marker = "    private boolean shortEdgesMode = false;"

    if marker not in source:
        fail(
            "Não encontrei o campo shortEdgesMode esperado."
        )

    fields = r'''
    private static final int LOVEGAME_MAX_DEPTH = 6;
    private static final int LOVEGAME_MAX_RESULTS = 32;

    private boolean storageSettingsOpened = false;
    private boolean waitingForAllFilesAccess = false;
    private boolean loveGameChoiceShowing = false;
'''

    if "LOVEGAME_MAX_DEPTH" not in source:
        source = source.replace(
            marker,
            marker + fields,
            1
        )

    return source


CHECK_LOVEGAME_METHOD = r'''    protected void checkLovegameFolder() {
        if (embed) {
            return;
        }

        Log.d("GameActivity", "Looking for lovegame/main.lua");

        /*
         * Preserve the official LÖVE Android app-specific location.
         */
        File ext = getExternalFilesDir("games");

        if (ext != null) {
            File appGame = new File(ext, "lovegame/main.lua");

            if (appGame.isFile() && appGame.canRead()) {
                gamePath = new File(ext, "lovegame").getAbsolutePath() + "/";
                storagePermissionUnnecessary = true;

                Log.d(
                    "GameActivity",
                    "Using app-specific lovegame: " + gamePath
                );

                return;
            }
        }

        /*
         * Android 11+:
         *
         * We need MANAGE_EXTERNAL_STORAGE to recursively inspect
         * shared storage.
         */
        if (android.os.Build.VERSION.SDK_INT >= 30) {

            if (!Environment.isExternalStorageManager()) {
                requestAllFilesAccess();
                return;
            }

        } else {

            /*
             * Preserve the old Android permission behavior.
             */
            if (!hasExternalStoragePermission()) {
                Log.d(
                    "GameActivity",
                    "Cannot scan shared storage: permission not granted"
                );

                return;
            }
        }

        File root = Environment.getExternalStorageDirectory();

        List<String> matches = findLovegameFolders(root);

        if (matches.isEmpty()) {
            Log.d(
                "GameActivity",
                "No lovegame/main.lua found under "
                    + root.getAbsolutePath()
            );

            showNoLovegameDialog();

            return;
        }

        /*
         * Remember the last selected LoveGame.
         */
        String lastPath = getSharedPreferences(
                "lovegame_launcher",
                Context.MODE_PRIVATE
        ).getString("last_path", "");

        if (lastPath.length() > 0) {

            File last = new File(lastPath, "main.lua");

            if (last.isFile() && last.canRead()) {

                gamePath =
                    last.getParentFile().getAbsolutePath()
                    + "/";

                storagePermissionUnnecessary = false;

                Log.d(
                    "GameActivity",
                    "Using remembered lovegame: "
                        + gamePath
                );

                return;
            }
        }

        /*
         * Exactly one LoveGame.
         */
        if (matches.size() == 1) {
            selectLovegameFolder(matches.get(0));
            return;
        }

        /*
         * Multiple LoveGames.
         */
        showLovegameChoices(matches);
    }

    private boolean hasAllFilesAccess() {
        if (android.os.Build.VERSION.SDK_INT < 30) {
            return true;
        }

        return Environment.isExternalStorageManager();
    }

    private void requestAllFilesAccess() {

        if (android.os.Build.VERSION.SDK_INT < 30) {
            return;
        }

        if (Environment.isExternalStorageManager()) {
            waitingForAllFilesAccess = false;
            return;
        }

        waitingForAllFilesAccess = true;

        if (storageSettingsOpened) {
            return;
        }

        storageSettingsOpened = true;

        runOnUiThread(new Runnable() {
            @Override
            public void run() {

                try {

                    /*
                     * Open the settings page specifically for THIS app.
                     */
                    Intent intent = new Intent(
                        Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION
                    );

                    intent.setData(
                        Uri.parse(
                            "package:" + getPackageName()
                        )
                    );

                    startActivity(intent);

                } catch (Exception firstException) {

                    Log.e(
                        "GameActivity",
                        "Could not open app-specific all-files settings",
                        firstException
                    );

                    /*
                     * Fallback to the general all-files page.
                     */
                    try {

                        Intent fallback = new Intent(
                            Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION
                        );

                        startActivity(fallback);

                    } catch (Exception secondException) {

                        Log.e(
                            "GameActivity",
                            "Could not open all-files settings",
                            secondException
                        );

                        showExternalStoragePermissionMissingDialog();
                    }
                }
            }
        });
    }

    private List<String> findLovegameFolders(File root) {

        LinkedHashSet<String> results =
            new LinkedHashSet<String>();

        Set<String> visited =
            new LinkedHashSet<String>();

        Deque<File> queue =
            new ArrayDeque<File>();

        Deque<Integer> depths =
            new ArrayDeque<Integer>();

        if (root == null || !root.isDirectory()) {
            return new ArrayList<String>();
        }

        queue.addLast(root);
        depths.addLast(0);

        while (
            !queue.isEmpty()
            && results.size() < LOVEGAME_MAX_RESULTS
        ) {

            File current = queue.removeFirst();
            int depth = depths.removeFirst();

            String currentPath;

            try {
                currentPath =
                    current.getCanonicalPath();
            } catch (IOException e) {
                currentPath =
                    current.getAbsolutePath();
            }

            /*
             * Prevent loops through symbolic links.
             */
            if (!visited.add(currentPath)) {
                continue;
            }

            /*
             * Found a directory called lovegame.
             */
            if (
                current.getName().equalsIgnoreCase("lovegame")
            ) {

                File main =
                    new File(current, "main.lua");

                if (
                    main.isFile()
                    && main.canRead()
                ) {

                    results.add(currentPath);

                    /*
                     * Do not scan inside a valid lovegame.
                     */
                    continue;
                }
            }

            if (depth >= LOVEGAME_MAX_DEPTH) {
                continue;
            }

            File[] children =
                current.listFiles();

            if (children == null) {
                continue;
            }

            for (File child : children) {

                if (!child.isDirectory()) {
                    continue;
                }

                String name =
                    child.getName();

                /*
                 * Ignore Android internals and hidden folders.
                 */
                if (
                    name.equals("Android")
                    || name.equals(".android")
                    || name.startsWith(".")
                ) {
                    continue;
                }

                queue.addLast(child);
                depths.addLast(depth + 1);
            }
        }

        ArrayList<String> sorted =
            new ArrayList<String>(results);

        Collections.sort(sorted);

        return sorted;
    }

    private void selectLovegameFolder(String folder) {

        File directory =
            new File(folder);

        File main =
            new File(directory, "main.lua");

        if (
            !directory.isDirectory()
            || !main.isFile()
            || !main.canRead()
        ) {

            Log.e(
                "GameActivity",
                "Invalid lovegame folder: " + folder
            );

            return;
        }

        gamePath =
            directory.getAbsolutePath()
            + "/";

        storagePermissionUnnecessary = false;

        getSharedPreferences(
                "lovegame_launcher",
                Context.MODE_PRIVATE
        )
        .edit()
        .putString(
            "last_path",
            directory.getAbsolutePath()
        )
        .apply();

        Log.d(
            "GameActivity",
            "Selected lovegame: " + gamePath
        );
    }

    private void showLovegameChoices(
        final List<String> matches
    ) {

        if (loveGameChoiceShowing) {
            return;
        }

        loveGameChoiceShowing = true;

        runOnUiThread(new Runnable() {
            @Override
            public void run() {

                String[] items =
                    new String[matches.size()];

                for (
                    int i = 0;
                    i < matches.size();
                    i++
                ) {
                    items[i] = matches.get(i);
                }

                AlertDialog dialog =
                    new AlertDialog.Builder(
                        GameActivity.this
                    )
                    .setTitle(
                        "Escolha o LoveGame"
                    )
                    .setItems(
                        items,
                        new DialogInterface.OnClickListener() {
                            @Override
                            public void onClick(
                                DialogInterface dialog,
                                int which
                            ) {

                                loveGameChoiceShowing =
                                    false;

                                selectLovegameFolder(
                                    matches.get(which)
                                );

                                restartLoveAfterSelection();
                            }
                        }
                    )
                    .setOnCancelListener(
                        new DialogInterface.OnCancelListener() {
                            @Override
                            public void onCancel(
                                DialogInterface dialog
                            ) {
                                loveGameChoiceShowing =
                                    false;
                            }
                        }
                    )
                    .create();

                dialog.show();
            }
        });
    }

    private void showNoLovegameDialog() {

        runOnUiThread(new Runnable() {
            @Override
            public void run() {

                new AlertDialog.Builder(
                    GameActivity.this
                )
                .setTitle(
                    "LoveGame não encontrado"
                )
                .setMessage(
                    "Não foi encontrada nenhuma pasta "
                    + "lovegame contendo main.lua.\n\n"
                    + "Crie uma pasta chamada lovegame "
                    + "em qualquer pasta do armazenamento "
                    + "e coloque o arquivo main.lua dentro dela."
                )
                .setPositiveButton(
                    "OK",
                    null
                )
                .show();
            }
        });
    }

    private void restartLoveAfterSelection() {

        if (gamePath.length() == 0) {
            return;
        }

        runOnUiThread(new Runnable() {
            @Override
            public void run() {

                try {

                    resetNative();
                    startNative();

                } catch (Exception e) {

                    Log.e(
                        "GameActivity",
                        "Failed to restart LÖVE",
                        e
                    );
                }
            }
        });
    }
'''


ON_RESUME_METHOD = r'''    @Override
    public void onResume() {
        super.onResume();

        /*
         * Android 11+ returns here after the user leaves the app
         * to enable "Allow access to manage all files".
         */
        if (
            !embed
            && waitingForAllFilesAccess
            && android.os.Build.VERSION.SDK_INT >= 30
        ) {

            if (Environment.isExternalStorageManager()) {

                Log.d(
                    "GameActivity",
                    "All-files access granted"
                );

                waitingForAllFilesAccess = false;
                storageSettingsOpened = false;

                /*
                 * Search again now that shared storage is accessible.
                 */
                gamePath = "";
                storagePermissionUnnecessary = false;

                checkLovegameFolder();

                /*
                 * If exactly one game was found and selected,
                 * restart the native LÖVE side with the new path.
                 *
                 * If several games were found, the selection
                 * dialog will call restartLoveAfterSelection().
                 */
                if (gamePath.length() > 0) {

                    try {
                        resetNative();
                        startNative();
                    } catch (Exception e) {
                        Log.e(
                            "GameActivity",
                            "Failed to restart after storage access",
                            e
                        );
                    }
                }
            }
        }
    }
'''


HAS_STORAGE_METHOD = r'''    @Keep
    public boolean hasExternalStoragePermission() {

        /*
         * Android 11+ uses the special all-files access AppOp.
         */
        if (android.os.Build.VERSION.SDK_INT >= 30) {
            return Environment.isExternalStorageManager();
        }

        /*
         * Preserve the official LÖVE behavior on Android 10
         * and earlier.
         */
        if (
            ActivityCompat.checkSelfPermission(
                this,
                Manifest.permission.READ_EXTERNAL_STORAGE
            ) == PackageManager.PERMISSION_GRANTED
        ) {
            return true;
        }

        Log.d(
            "GameActivity",
            "Requesting legacy external storage permission"
        );

        ActivityCompat.requestPermissions(
            this,
            new String[]{
                Manifest.permission.READ_EXTERNAL_STORAGE
            },
            EXTERNAL_STORAGE_REQUEST_CODE
        );

        synchronized (externalStorageRequestDummy) {

            try {
                externalStorageRequestDummy.wait();
            } catch (InterruptedException e) {

                Log.d(
                    "GameActivity",
                    "requesting external storage permission",
                    e
                );

                return false;
            }
        }

        return ActivityCompat.checkSelfPermission(
            this,
            Manifest.permission.READ_EXTERNAL_STORAGE
        ) == PackageManager.PERMISSION_GRANTED;
    }
'''


def patch_manifest():
    if not MANIFEST.exists():
        fail(
            "AndroidManifest.xml não encontrado:\n"
            + str(MANIFEST)
        )

    text = MANIFEST.read_text(
        encoding="utf-8"
    )

    permission = (
        '<uses-permission '
        'android:name="android.permission.MANAGE_EXTERNAL_STORAGE" />'
    )

    if permission not in text:

        manifest_match = re.search(
            r"<manifest\b[^>]*>",
            text,
            re.DOTALL
        )

        if not manifest_match:
            fail(
                "Não encontrei a tag <manifest> no AndroidManifest.xml."
            )

        insert_at = manifest_match.end()

        text = (
            text[:insert_at]
            + "\n    "
            + permission
            + "\n"
            + text[insert_at:]
        )

        MANIFEST.write_text(
            text,
            encoding="utf-8"
        )

        print(
            "Manifest: MANAGE_EXTERNAL_STORAGE adicionada."
        )

    else:
        print(
            "Manifest: MANAGE_EXTERNAL_STORAGE já existe."
        )


def patch_game_activity():
    if not GAME_ACTIVITY.exists():
        fail(
            "GameActivity.java não encontrado:\n"
            + str(GAME_ACTIVITY)
        )

    print(
        "GameActivity encontrado:"
    )
    print(
        " ",
        GAME_ACTIVITY
    )

    source = GAME_ACTIVITY.read_text(
        encoding="utf-8"
    )

    /*
    """
    Backup único do arquivo original.
    """
    */

    backup = GAME_ACTIVITY.with_suffix(
        ".java.lovegame-original"
    )

    if not backup.exists():
        shutil.copy2(
            GAME_ACTIVITY,
            backup
        )

        print(
            "Backup criado:"
        )
        print(
            " ",
            backup
        )

    source = add_java_imports(source)

    source = add_fields(source)

    source = replace_method(
        source,
        "    protected void checkLovegameFolder()",
        CHECK_LOVEGAME_METHOD
    )

    source = replace_method(
        source,
        "    @Override\n    public void onResume()",
        ON_RESUME_METHOD
    )

    source = replace_method(
        source,
        "    @Keep\n    public boolean hasExternalStoragePermission()",
        HAS_STORAGE_METHOD
    )

    GAME_ACTIVITY.write_text(
        source,
        encoding="utf-8"
    )

    print(
        "GameActivity.java atualizado."
    )


def verify():
    game_text = GAME_ACTIVITY.read_text(
        encoding="utf-8"
    )

    manifest_text = MANIFEST.read_text(
        encoding="utf-8"
    )

    required_java = [
        "LOVEGAME_MAX_DEPTH",
        "requestAllFilesAccess",
        "findLovegameFolders",
        "showLovegameChoices",
        "Environment.isExternalStorageManager()",
        "ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION",
        "last_path",
    ]

    for item in required_java:
        if item not in game_text:
            fail(
                "Verificação falhou. "
                "Código esperado não encontrado: "
                + item
            )

    permission = (
        "android.permission.MANAGE_EXTERNAL_STORAGE"
    )

    if permission not in manifest_text:
        fail(
            "Verificação falhou: "
            "MANAGE_EXTERNAL_STORAGE não está no Manifest."
        )

    print("")
    print("==============================================")
    print(" LOVEGAME PATCH APLICADO COM SUCESSO")
    print("==============================================")
    print("")
    print("LÖVE: 11.5a")
    print("Busca: lovegame/main.lua")
    print("Profundidade máxima:", 6)
    print("Máximo de resultados:", 32)
    print("Acesso especial: MANAGE_EXTERNAL_STORAGE")
    print("Seleção múltipla: SIM")
    print("Última seleção salva: SIM")
    print("")


def main():
    print("")
    print("==============================================")
    print(" LÖVE 11.5 LoveGame Launcher Patch")
    print("==============================================")
    print("")

    if not ROOT.exists():
        fail(
            "Raiz do projeto não encontrada."
        )

    patch_game_activity()
    patch_manifest()
    verify()


if __name__ == "__main__":
    main()
