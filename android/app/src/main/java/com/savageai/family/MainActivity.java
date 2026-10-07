package com.savageai.family;

import android.app.Activity;
import android.app.PendingIntent;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Insets;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.util.Base64;
import android.view.Gravity;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.lang.ref.WeakReference;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;

public class MainActivity extends Activity {
    private static final String SAVAGE_ROOT = "/data/local/savage-ai";

    private static final String TERMUX_PERMISSION = "com.termux.permission.RUN_COMMAND";
    private static final String TERMUX_PACKAGE = "com.termux";
    private static final String TERMUX_SERVICE = "com.termux.app.RunCommandService";
    private static final String TERMUX_ACTION = "com.termux.RUN_COMMAND";
    private static final String EXTRA_PATH = "com.termux.RUN_COMMAND_PATH";
    private static final String EXTRA_ARGUMENTS = "com.termux.RUN_COMMAND_ARGUMENTS";
    private static final String EXTRA_WORKDIR = "com.termux.RUN_COMMAND_WORKDIR";
    private static final String EXTRA_BACKGROUND = "com.termux.RUN_COMMAND_BACKGROUND";
    private static final String EXTRA_PENDING_INTENT = "com.termux.RUN_COMMAND_PENDING_INTENT";

    private static final int REQUEST_TERMUX_PERMISSION = 7001;
    private static final AtomicInteger EXECUTION_ID = new AtomicInteger(1000);
    private static WeakReference<MainActivity> activeActivity = new WeakReference<>(null);

    private static final int BG = Color.rgb(6, 11, 15);
    private static final int PANEL = Color.rgb(13, 23, 29);
    private static final int PANEL_2 = Color.rgb(18, 31, 38);
    private static final int TEXT = Color.rgb(215, 241, 239);
    private static final int MUTED = Color.rgb(132, 160, 163);
    private static final int ACCENT = Color.rgb(105, 232, 215);
    private static final int ACCENT_DARK = Color.rgb(21, 69, 65);
    private static final int DANGER = Color.rgb(255, 126, 126);

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
        subtitle.setText("TERMUX-NATIVE ROOT AGENT");
        subtitle.setTextColor(MUTED);
        subtitle.setTextSize(11);
        subtitle.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        subtitle.setLetterSpacing(0.10f);
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
        backend.setText("backend: Termux");
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
        output.setText("Savage Android frontend ready.\nBackend mode: native Termux RUN_COMMAND.\n");
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

        root.addView(consoleCard, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));

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

        ensureTermuxPermission();
    }

    @Override
    protected void onStart() {
        super.onStart();
        activeActivity = new WeakReference<>(this);
    }

    @Override
    protected void onStop() {
        MainActivity current = activeActivity.get();
        if (current == this) activeActivity.clear();
        super.onStop();
    }

    private void ensureTermuxPermission() {
        if (Build.VERSION.SDK_INT >= 23 &&
                checkSelfPermission(TERMUX_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{TERMUX_PERMISSION}, REQUEST_TERMUX_PERMISSION);
        } else {
            checkEnvironment();
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_TERMUX_PERMISSION) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                append("\nTermux command permission granted.\n");
                checkEnvironment();
            } else {
                status.setText("TERMUX PERMISSION");
                backend.setText("backend: blocked");
                append("\nGrant Savage AI the 'Run commands in Termux environment' permission in App info.\n");
            }
        }
    }

    private void applyInsets(LinearLayout root) {
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            int left = dp(16), top = dp(10), right = dp(16), bottom = dp(12);

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

        String b64 = Base64.encodeToString(
                prompt.getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP);

        String script =
                "export SAVAGE_PROMPT_B64='" + b64 + "'; "
                + "BRIDGE=\"$HOME/.local/bin/savage-app-bridge\"; "
                + "if [ ! -x \"$BRIDGE\" ]; then "
                + "echo 'SAVAGE BRIDGE MISSING: install it from Termux'; exit 127; "
                + "fi; "
                + "exec \"$BRIDGE\" prompt";

        runInTermux("prompt", script);
    }

    private void checkEnvironment() {
        status.setText("CHECKING…");
        backend.setText("backend: Termux");

        String script =
                "BRIDGE=\"$HOME/.local/bin/savage-app-bridge\"; "
                + "if [ ! -x \"$BRIDGE\" ]; then "
                + "echo 'SAVAGE BRIDGE MISSING: install it from Termux'; exit 127; "
                + "fi; "
                + "exec \"$BRIDGE\" status";

        runInTermux("status", script);
    }

    private void stopInference() {
        send.setEnabled(true);
        status.setText("STOPPING…");
        runInTermux("stop",
                "BRIDGE=\"$HOME/.local/bin/savage-app-bridge\"; "
                + "if [ -x \"$BRIDGE\" ]; then exec \"$BRIDGE\" stop; "
                + "else pkill -INT -f '/data/local/savage-ai/bin/llama/llama-cli' 2>/dev/null || true; "
                + "echo 'STOP sent'; fi");
    }

    private void runInTermux(String kind, String script) {
        if (Build.VERSION.SDK_INT >= 23 &&
                checkSelfPermission(TERMUX_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            status.setText("TERMUX PERMISSION");
            backend.setText("backend: blocked");
            append("\nMissing Termux RUN_COMMAND permission.\n");
            ensureTermuxPermission();
            return;
        }

        int executionId = EXECUTION_ID.getAndIncrement();

        Intent callbackIntent = new Intent(this, PluginResultsService.class);
        callbackIntent.putExtra("execution_id", executionId);
        callbackIntent.putExtra("request_kind", kind);

        int flags = PendingIntent.FLAG_ONE_SHOT;
        if (Build.VERSION.SDK_INT >= 31) flags |= PendingIntent.FLAG_MUTABLE;

        PendingIntent pendingIntent = PendingIntent.getService(
                this, executionId, callbackIntent, flags);

        Intent intent = new Intent();
        intent.setClassName(TERMUX_PACKAGE, TERMUX_SERVICE);
        intent.setAction(TERMUX_ACTION);
        intent.putExtra(EXTRA_PATH, "$PREFIX/bin/bash");
        intent.putExtra(EXTRA_ARGUMENTS, new String[]{"-lc", script});
        intent.putExtra(EXTRA_WORKDIR, "~/");
        intent.putExtra(EXTRA_BACKGROUND, true);
        intent.putExtra(EXTRA_PENDING_INTENT, pendingIntent);

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent);
            } else {
                startService(intent);
            }
        } catch (SecurityException e) {
            status.setText("TERMUX SETUP");
            backend.setText("backend: blocked");
            append("\nTermux rejected RUN_COMMAND. In Termux set allow-external-apps=true, "
                    + "reload settings, then grant Savage AI the Termux command permission.\n");
            setBusy(false);
        } catch (Exception e) {
            status.setText("TERMUX OFFLINE");
            backend.setText("backend: unavailable");
            append("\nCould not start Termux command service: " + e.getMessage() + "\n");
            setBusy(false);
        }
    }

    public static void deliverTermuxResult(
            String kind, String stdout, String stderr,
            int exitCode, int errCode, String errMsg) {

        MainActivity activity = activeActivity.get();
        if (activity == null) return;

        activity.runOnUiThread(() ->
                activity.handleTermuxResult(kind, stdout, stderr, exitCode, errCode, errMsg));
    }

    private void handleTermuxResult(
            String kind, String stdout, String stderr,
            int exitCode, int errCode, String errMsg) {

        String out = stdout == null ? "" : stdout.trim();
        String err = stderr == null ? "" : stderr.trim();
        String internal = errMsg == null ? "" : errMsg.trim();

        if ("status".equals(kind)) {
            String combined = out + "\n" + err + "\n" + internal;

            boolean termux = combined.contains("prefix=") && combined.contains("python=");
            boolean root = combined.contains("uid=0");
            boolean savage = combined.contains("core: READY")
                    && combined.contains("model: READY")
                    && combined.contains("llama.cpp: READY");

            boolean ok = exitCode == 0 && errCode <= 0 && termux && root && savage;

            status.setText(ok ? "ROOT • READY" : "SETUP ISSUE");
            status.setBackground(roundRect(
                    ok ? ACCENT_DARK : Color.rgb(84, 43, 46),
                    ok ? ACCENT_DARK : Color.rgb(84, 43, 46),
                    99));
            backend.setText(termux ? "backend: Termux native" : "backend: unavailable");

            if (!out.isEmpty()) append("\n" + out + "\n");
            if (!err.isEmpty()) append("\nstderr:\n" + err + "\n");
            if (!internal.isEmpty()) append("\nTermux: " + internal + "\n");
            return;
        }

        if ("stop".equals(kind)) {
            append("\n" + (out.isEmpty() ? "[STOP sent]" : out) + "\n");
            setBusy(false);
            return;
        }

        if (!out.isEmpty()) append(out + "\n");
        if (!err.isEmpty()) append("stderr:\n" + err + "\n");
        if (!internal.isEmpty()) append("Termux: " + internal + "\n");

        if (exitCode != 0 || errCode > 0) {
            append("[exit=" + exitCode + ", termuxErr=" + errCode + "]\n");
        }

        setBusy(false);
    }

    private void setBusy(boolean busy) {
        send.setEnabled(!busy);
        send.setAlpha(busy ? 0.55f : 1f);
        status.setText(busy ? "THINKING…" : "ROOT • READY");
        backend.setText(busy ? "backend: Termux + llama.cpp" : "backend: Termux native");
    }

    private void append(String s) {
        output.append(s);
        scroll.post(() -> scroll.fullScroll(ScrollView.FOCUS_DOWN));
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }
}
