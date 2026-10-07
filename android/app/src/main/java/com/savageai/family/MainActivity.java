package com.savageai.family;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Insets;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final String SAVAGE_ROOT = "/data/local/savage-ai";

    private static final int BG = Color.rgb(6, 11, 15);
    private static final int PANEL = Color.rgb(13, 23, 29);
    private static final int PANEL_2 = Color.rgb(18, 31, 38);
    private static final int TEXT = Color.rgb(215, 241, 239);
    private static final int MUTED = Color.rgb(132, 160, 163);
    private static final int ACCENT = Color.rgb(105, 232, 215);
    private static final int ACCENT_DARK = Color.rgb(21, 69, 65);
    private static final int DANGER = Color.rgb(255, 126, 126);

    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private volatile Process currentProcess;

    private TextView output;
    private TextView status;
    private TextView backend;
    private EditText input;
    private Button send;
    private ScrollView scroll;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);

        Window w = getWindow();
        w.setStatusBarColor(BG);
        w.setNavigationBarColor(BG);
        w.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);
        root.setPadding(dp(16), dp(10), dp(16), dp(12));

        applyInsets(root);

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.VERTICAL);
        header.setPadding(dp(2), 0, dp(2), dp(12));

        TextView title = new TextView(this);
        title.setText("SAVAGE AI");
        title.setTextColor(ACCENT);
        title.setTextSize(28);
        title.setTypeface(Typeface.create("sans-serif-black", Typeface.BOLD));
        header.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("LOCAL ROOT AGENT");
        subtitle.setTextColor(MUTED);
        subtitle.setTextSize(11);
        subtitle.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        subtitle.setLetterSpacing(0.12f);
        header.addView(subtitle);

        LinearLayout statusRow = new LinearLayout(this);
        statusRow.setOrientation(LinearLayout.HORIZONTAL);
        statusRow.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams statusRowLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        statusRowLp.topMargin = dp(10);
        header.addView(statusRow, statusRowLp);

        status = new TextView(this);
        status.setText("CHECKING…");
        status.setTextColor(TEXT);
        status.setTextSize(11);
        status.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        status.setPadding(dp(10), dp(6), dp(10), dp(6));
        status.setBackground(roundRect(ACCENT_DARK, ACCENT_DARK, 99));
        statusRow.addView(status);

        backend = new TextView(this);
        backend.setText("backend: probing");
        backend.setTextColor(MUTED);
        backend.setTextSize(11);
        backend.setTypeface(Typeface.MONOSPACE);
        backend.setGravity(Gravity.END);
        LinearLayout.LayoutParams backendLp = new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        backendLp.leftMargin = dp(10);
        statusRow.addView(backend, backendLp);

        root.addView(header);

        LinearLayout consoleCard = new LinearLayout(this);
        consoleCard.setOrientation(LinearLayout.VERTICAL);
        consoleCard.setPadding(dp(12), dp(10), dp(12), dp(10));
        consoleCard.setBackground(roundRect(PANEL, Color.rgb(28, 47, 55), 18));

        TextView consoleLabel = new TextView(this);
        consoleLabel.setText("CONSOLE");
        consoleLabel.setTextColor(MUTED);
        consoleLabel.setTextSize(10);
        consoleLabel.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        consoleCard.addView(consoleLabel);

        output = new TextView(this);
        output.setTextColor(TEXT);
        output.setTextSize(13);
        output.setTypeface(Typeface.MONOSPACE);
        output.setText("Savage Android controller ready.\n");
        output.setTextIsSelectable(true);
        output.setPadding(0, dp(8), 0, dp(4));
        output.setLineSpacing(0f, 1.10f);

        scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.addView(output, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT,
                ScrollView.LayoutParams.WRAP_CONTENT));
        consoleCard.addView(scroll, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));

        LinearLayout.LayoutParams consoleLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f);
        root.addView(consoleCard, consoleLp);

        input = new EditText(this);
        input.setHint("Ask Savage…  e.g. recon: auto: inspect memory");
        input.setHintTextColor(Color.rgb(103, 124, 128));
        input.setTextColor(Color.WHITE);
        input.setTextSize(15);
        input.setSingleLine(false);
        input.setMinLines(2);
        input.setMaxLines(4);
        input.setGravity(Gravity.TOP | Gravity.START);
        input.setBackground(roundRect(PANEL_2, Color.rgb(38, 58, 66), 16));
        input.setPadding(dp(13), dp(11), dp(13), dp(11));

        LinearLayout.LayoutParams inputLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        inputLp.topMargin = dp(10);
        root.addView(input, inputLp);

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        buttons.setGravity(Gravity.CENTER_VERTICAL);

        send = makeButton("SEND", true, false);
        Button check = makeButton("STATUS", false, false);
        Button stop = makeButton("STOP", false, true);
        Button clear = makeButton("CLEAR", false, false);

        buttons.addView(send, weighted());
        buttons.addView(check, weighted());
        buttons.addView(stop, weighted());
        buttons.addView(clear, weighted());

        LinearLayout.LayoutParams buttonsLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        buttonsLp.topMargin = dp(8);
        root.addView(buttons, buttonsLp);

        setContentView(root);

        send.setOnClickListener(v -> submit());
        check.setOnClickListener(v -> checkEnvironment());
        stop.setOnClickListener(v -> stopInference());
        clear.setOnClickListener(v -> output.setText(""));

        checkEnvironment();
    }

    private void applyInsets(LinearLayout root) {
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            int left = dp(16);
            int top = dp(10);
            int right = dp(16);
            int bottom = dp(12);

            if (Build.VERSION.SDK_INT >= 30) {
                Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                Insets ime = insets.getInsets(WindowInsets.Type.ime());
                left += bars.left;
                top += bars.top;
                right += bars.right;
                bottom += Math.max(bars.bottom, ime.bottom);
            } else {
                left += insets.getSystemWindowInsetLeft();
                top += insets.getSystemWindowInsetTop();
                right += insets.getSystemWindowInsetRight();
                bottom += insets.getSystemWindowInsetBottom();
            }

            v.setPadding(left, top, right, bottom);
            return insets;
        });
    }

    private LinearLayout.LayoutParams weighted() {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, dp(48), 1f);
        lp.setMargins(dp(3), 0, dp(3), 0);
        return lp;
    }

    private Button makeButton(String text, boolean primary, boolean danger) {
        Button b = new Button(this);
        b.setText(text);
        b.setTextSize(11);
        b.setAllCaps(true);
        b.setTypeface(Typeface.create("sans-serif-medium", Typeface.BOLD));
        b.setPadding(dp(4), 0, dp(4), 0);

        if (primary) {
            b.setTextColor(BG);
            b.setBackground(roundRect(ACCENT, ACCENT, 14));
        } else if (danger) {
            b.setTextColor(DANGER);
            b.setBackground(roundRect(PANEL_2, Color.rgb(91, 48, 52), 14));
        } else {
            b.setTextColor(TEXT);
            b.setBackground(roundRect(PANEL_2, Color.rgb(42, 63, 70), 14));
        }
        return b;
    }

    private GradientDrawable roundRect(int fill, int stroke, int radiusDp) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(fill);
        d.setCornerRadius(dp(radiusDp));
        d.setStroke(dp(1), stroke);
        return d;
    }

    private void submit() {
        final String prompt = input.getText().toString().trim();
        if (prompt.isEmpty()) return;

        input.setText("");
        append("\n› " + prompt + "\n");
        setBusy(true);

        worker.execute(() -> {
            String result;
            try {
                result = runRoot(buildPromptCommand(prompt));
            } catch (Exception e) {
                result = "ERROR: " + e;
            }

            final String finalResult = result;
            runOnUiThread(() -> {
                append(finalResult + "\n");
                setBusy(false);
            });
        });
    }

    private void checkEnvironment() {
        status.setText("CHECKING…");
        backend.setText("backend: probing");

        worker.execute(() -> {
            String command = ensureMounted()
                    + "echo '--- ROOT ---'; id; "
                    + "echo '--- SAVAGE ---'; "
                    + "if [ -f " + SAVAGE_ROOT + "/savage-family/savage/cli.py ]; "
                    + "then echo 'core: READY'; else echo 'core: MISSING'; fi; "
                    + "if [ -f " + SAVAGE_ROOT + "/models/Qwen3-1.7B-abliterated-Q4_K_M.gguf ]; "
                    + "then echo 'model: READY'; else echo 'model: MISSING'; fi; "
                    + "if [ -x " + SAVAGE_ROOT + "/bin/llama/llama-cli ]; "
                    + "then echo 'llama.cpp: READY'; else echo 'llama.cpp: MISSING'; fi; "
                    + pythonResolver()
                    + "echo \"python: READY ($PY)\"; \"$PY\" -V 2>&1";

            String result;
            try {
                result = runRoot(command);
            } catch (Exception e) {
                result = "Root check failed: " + e;
            }

            final String finalResult = result;
            runOnUiThread(() -> {
                boolean ok = finalResult.contains("uid=0")
                        && finalResult.contains("core: READY")
                        && finalResult.contains("model: READY")
                        && finalResult.contains("llama.cpp: READY")
                        && finalResult.contains("python: READY");

                status.setText(ok ? "ROOT • READY" : "SETUP ISSUE");
                status.setBackground(roundRect(
                        ok ? ACCENT_DARK : Color.rgb(84, 43, 46),
                        ok ? ACCENT_DARK : Color.rgb(84, 43, 46),
                        99));

                String py = extractPythonPath(finalResult);
                backend.setText(ok
                        ? (py.isEmpty() ? "backend: local" : "backend: " + shortPath(py))
                        : "backend: unavailable");

                append(finalResult + "\n");
            });
        });
    }

    private String buildPromptCommand(String prompt) {
        String b64 = Base64.encodeToString(
                prompt.getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP);

        String pyCode =
                "import os,base64;"
                + "from savage.config import Config;"
                + "from savage.cli import App;"
                + "p=base64.b64decode(os.environ[\"SAVAGE_PROMPT_B64\"]).decode(\"utf-8\");"
                + "a=App(Config());"
                + "r=a.cmd.handle(a.sid,p);"
                + "print(r[\"output\"]);"
                + "a.close()";

        return ensureMounted()
                + pythonResolver()
                + "export SAVAGE_AI_ROOT='" + SAVAGE_ROOT + "'; "
                + "export PYTHONPATH='" + SAVAGE_ROOT + "/savage-family'; "
                + "export SAVAGE_PROMPT_B64='" + b64 + "'; "
                + "export PATH='/data/data/com.termux/files/usr/bin:/data/user/0/com.termux/files/usr/bin:/system/bin:/system/xbin:'\"$PATH\"; "
                + "export HOME='/data/data/com.termux/files/home'; "
                + "\"$PY\" -c '" + pyCode + "' 2>&1";
    }

    private String pythonResolver() {
        return "PY=''; "
                + "for P in "
                + SAVAGE_ROOT + "/venv/bin/python3 "
                + SAVAGE_ROOT + "/venv/bin/python "
                + "/data/data/com.termux/files/usr/bin/python3 "
                + "/data/user/0/com.termux/files/usr/bin/python3 "
                + "/data/data/com.termux/files/usr/bin/python "
                + "/data/user/0/com.termux/files/usr/bin/python; do "
                + "if [ -e \"$P\" ]; then "
                + "\"$P\" -V >/dev/null 2>&1 && { PY=\"$P\"; break; }; "
                + "fi; done; "
                + "if [ -z \"$PY\" ]; then "
                + "for P in /data/data/com.termux/files/usr/bin/python3.* /data/user/0/com.termux/files/usr/bin/python3.*; do "
                + "[ -e \"$P\" ] || continue; "
                + "\"$P\" -V >/dev/null 2>&1 && { PY=\"$P\"; break; }; "
                + "done; fi; "
                + "if [ -z \"$PY\" ]; then "
                + "echo '__SAVAGE_ERROR__: no runnable Python found'; exit 127; "
                + "fi; ";
    }

    private String ensureMounted() {
        return "if [ ! -f " + SAVAGE_ROOT + "/savage-family/savage/cli.py ]; then "
                + "IMG=$(find /mnt/media_rw -maxdepth 2 -type f -name savage-ai.img 2>/dev/null | head -n1); "
                + "if [ -n \"$IMG\" ]; then "
                + "mkdir -p " + SAVAGE_ROOT + "; "
                + "LOOP=$(losetup -j \"$IMG\" 2>/dev/null | head -n1 | cut -d: -f1); "
                + "if [ -z \"$LOOP\" ]; then LOOP=$(losetup -f); losetup \"$LOOP\" \"$IMG\"; fi; "
                + "mount -t ext4 -o rw,exec \"$LOOP\" " + SAVAGE_ROOT + " 2>/dev/null || true; "
                + "fi; fi; ";
    }

    private Process startRootProcess(String command) throws Exception {
        // Android app processes do not inherit Termux's PATH. KernelSU/Magisk-style
        // su may still be mounted at an absolute system path, so probe those first.
        String[] candidates = new String[] {
                "/system/bin/su",
                "/system/xbin/su",
                "/sbin/su",
                "/su/bin/su",
                "/data/adb/ksu/bin/su",
                "/debug_ramdisk/su"
        };

        Exception last = null;

        for (String candidate : candidates) {
            try {
                ProcessBuilder pb = new ProcessBuilder(candidate, "-c", command);
                pb.redirectErrorStream(true);
                return pb.start();
            } catch (Exception e) {
                last = e;
            }
        }

        // Final fallback: ask Android's system shell to resolve su from a broad PATH.
        try {
            ProcessBuilder pb = new ProcessBuilder(
                    "/system/bin/sh",
                    "-c",
                    "export PATH=/system/bin:/system/xbin:/sbin:/su/bin:/data/adb/ksu/bin:$PATH; " +
                    "exec su -c \"$1\"",
                    "sh",
                    command
            );
            pb.redirectErrorStream(true);
            return pb.start();
        } catch (Exception e) {
            last = e;
        }

        throw new java.io.IOException(
                "No root su binary found. Checked KernelSU/system su paths.",
                last
        );
    }

    private String runRoot(String command) throws Exception {
        Process process = startRootProcess(command);
        currentProcess = process;

        StringBuilder sb = new StringBuilder();
        try (BufferedReader br = new BufferedReader(
                new InputStreamReader(process.getInputStream()))) {
            String line;
            while ((line = br.readLine()) != null) {
                if (sb.length() < 65536) {
                    sb.append(line).append('\n');
                }
            }
        }

        int rc = process.waitFor();
        currentProcess = null;

        if (sb.length() == 0) {
            sb.append("(no output; rc=").append(rc).append(")");
        }
        return sb.toString().trim();
    }

    private void stopInference() {
        Process p = currentProcess;
        if (p != null) p.destroy();

        worker.execute(() -> {
            try {
                runRoot("pkill -INT -f '/data/local/savage-ai/bin/llama/llama-cli' 2>/dev/null || true");
            } catch (Exception ignored) {
            }

            runOnUiThread(() -> {
                append("\n[STOP requested]\n");
                setBusy(false);
            });
        });
    }

    private void setBusy(boolean busy) {
        send.setEnabled(!busy);
        send.setAlpha(busy ? 0.55f : 1f);
        status.setText(busy ? "THINKING…" : "ROOT • READY");
        backend.setText(busy ? "backend: llama.cpp" : backend.getText());
    }

    private void append(String s) {
        output.append(s);
        scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
    }

    private String extractPythonPath(String text) {
        String marker = "python: READY (";
        int start = text.indexOf(marker);
        if (start < 0) return "";
        start += marker.length();
        int end = text.indexOf(')', start);
        if (end < 0) return "";
        return text.substring(start, end);
    }

    private String shortPath(String path) {
        if (path.contains("termux")) return "Termux Python";
        if (path.contains("/venv/")) return "Savage venv";
        return "local Python";
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    @Override
    protected void onDestroy() {
        Process p = currentProcess;
        if (p != null) p.destroy();
        worker.shutdownNow();
        super.onDestroy();
    }
}
