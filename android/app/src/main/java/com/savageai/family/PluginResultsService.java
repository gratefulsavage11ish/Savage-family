package com.savageai.family;

import android.app.IntentService;
import android.content.Intent;
import android.os.Bundle;

public class PluginResultsService extends IntentService {
    public PluginResultsService() {
        super("SavageTermuxResults");
    }

    @Override
    protected void onHandleIntent(Intent intent) {
        if (intent == null) return;

        String kind = intent.getStringExtra("request_kind");
        Bundle result = intent.getBundleExtra("result");

        if (result == null) {
            MainActivity.deliverTermuxResult(
                    kind == null ? "" : kind,
                    "", "", -1, 1,
                    "Termux returned no result bundle");
            return;
        }

        MainActivity.deliverTermuxResult(
                kind == null ? "" : kind,
                result.getString("stdout", ""),
                result.getString("stderr", ""),
                result.getInt("exitCode", -1),
                result.getInt("err", -1),
                result.getString("errmsg", ""));
    }
}
