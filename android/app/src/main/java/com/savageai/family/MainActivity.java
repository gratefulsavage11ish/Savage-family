package com.savageai.family;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.widget.Button;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
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
    private static final String PYTHON = "/data/data/com.termux/files/usr/bin/python";
    private static final int BG = Color.rgb(8, 13, 17);
    private static final int PANEL = Color.rgb(16, 24, 30);
    private static final int TEXT = Color.rgb(184, 232, 230);
    private static final int ACCENT = Color.rgb(121, 221, 208);

    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private volatile Process currentProcess;

    private TextView output;
    private TextView status;
    private EditText input;
    private Button send;
    private ScrollView scroll;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);

        Window w = getWindow();
        w.setStatusBarColor(BG);
        w.setNavigationBarColor(BG);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(14), dp(12), dp(14), dp(12));
        root.setBackgroundColor(BG);

        TextView title = new TextView(this);
        title.setText("SAVAGE AI");
        title.setTextColor(ACCENT);
        title.setTextSize(25);
        title.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        root.addView(title);

        status = new TextView(this);
        status.setText("Checking root + Savage environment...");
        status.setTextColor(Color.LTGRAY);
        status.setTextSize(12);
        status.setTypeface(Typeface.MONOSPACE);
        status.setPadding(0, dp(3), 0, dp(10));
        root.addView(status);

        output = new TextView(this);
        output.setTextColor(TEXT);
        output.setTextSize(14);
        output.setTypeface(Typeface.MONOSPACE);
        output.setText("Savage Android controller\n\n");
        output.setTextIsSelectable(true);
        output.setPadding(dp(10), dp(10), dp(10), dp(10));

        HorizontalScrollView hscroll = new HorizontalScrollView(this);
        hscroll.setFillViewport(true);
        hscroll.addView(output, new HorizontalScrollView.LayoutParams(
                HorizontalScrollView.LayoutParams.MATCH_PARENT,
                HorizontalScrollView.LayoutParams.WRAP_CONTENT));

        scroll = new ScrollView(this);
        scroll.setBackgroundColor(PANEL);
        scroll.addView(hscroll);
        root.addView(scroll, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));

        input = new EditText(this);
        input.setHint("Ask Savage…  e.g. recon: auto: inspect memory");
        input.setHintTextColor(Color.GRAY);
        input.setTextColor(Color.WHITE);
        input.setSingleLine(false);
        input.setMinLines(2);
        input.setMaxLines(5);
        input.setGravity(Gravity.TOP);
        input.setBackgroundColor(PANEL);
        input.setPadding(dp(10), dp(10), dp(10), dp(10));
        LinearLayout.LayoutParams inputLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        inputLp.topMargin = dp(10);
        root.addView(input, inputLp);

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        buttons.setGravity(Gravity.CENTER_VERTICAL);

        send = makeButton("SEND");
        Button check = makeButton("STATUS");
        Button stop = makeButton("STOP");
        Button clear = makeButton("CLEAR");

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

    private LinearLayout.LayoutParams weighted() {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, dp(48), 1f);
        lp.setMargins(dp(2), 0, dp(2), 0);
        return lp;
    }

    private Button makeButton(String text) {
        Button b = new Button(this);
        b.setText(text);
        b.setTextSize(11);
        b.setAllCaps(false);
        return b;
    }

    private void submit() {
        final String prompt = input.getText().toString().trim();
        if (prompt.isEmpty()) return;

        input.setText("");
        append("\nSavage > " + prompt + "\n");
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
        status.setText("Checking...");
        worker.execute(() -> {
            String command = ensureMounted()
                    + "echo '--- ROOT ---'; id; "
                    + "echo '--- SAVAGE ---'; "
                    + "if [ -f " + SAVAGE_ROOT + "/savage-family/savage/cli.py ]; "
                    + "then echo 'core: READY'; else echo 'core: MISSING'; fi; "
                    + "if [ -f " + SAVAGE_ROOT + "/models/Qwen3-1.7B-abliterated-Q4_K_M.gguf ]; "
                    + "then echo 'model: READY'; else echo 'model: MISSING'; fi; "
                    + "if [ -x " + SAVAGE_ROOT + "/bin/llama/llama-cli ]; "
                    + "then echo 'llama.cpp: READY'; else echo 'llama.cpp: MISSING'; fi";
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
                        && finalResult.contains("model: READY");
                status.setText(ok ? "ROOT • SAVAGE READY" : "SETUP NEEDS ATTENTION");
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
                + "p=base64.b64decode(os.environ['SAVAGE_PROMPT_B64']).decode('utf-8');"
                + "a=App(Config());"
                + "r=a.cmd.handle(a.sid,p);"
                + "print(r['output']);"
                + "a.close()";

        return ensureMounted()
                + "export SAVAGE_AI_ROOT='" + SAVAGE_ROOT + "'; "
                + "export PYTHONPATH='" + SAVAGE_ROOT + "/savage-family'; "
                + "export SAVAGE_PROMPT_B64='" + b64 + "'; "
                + PYTHON + " -c \"" + pyCode + "\" 2>&1";
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

    private String runRoot(String command) throws Exception {
        ProcessBuilder pb = new ProcessBuilder("su", "-c", command);
        pb.redirectErrorStream(true);
        Process process = pb.start();
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
                new ProcessBuilder(
                        "su", "-c",
                        "pkill -INT -f '/data/local/savage-ai/bin/llama/llama-cli' 2>/dev/null || true"
                ).start().waitFor();
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
        status.setText(busy ? "SAVAGE THINKING…" : "ROOT • SAVAGE READY");
    }

    private void append(String s) {
        output.append(s);
        scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
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
