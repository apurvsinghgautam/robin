'use client';

import { Settings, Key, Database, Shield } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div className="min-h-screen bg-slate-950 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <Settings className="h-8 w-8 text-blue-400" />
          <h1 className="text-2xl font-bold text-slate-100">Settings</h1>
        </div>

        <div className="space-y-6">
          {/* API Configuration */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
            <div className="flex items-center gap-3 mb-4">
              <Key className="h-5 w-5 text-yellow-400" />
              <h2 className="text-lg font-semibold text-slate-100">API Configuration</h2>
            </div>
            <p className="text-slate-400 text-sm mb-4">
              Configure your Anthropic API key or Claude OAuth token for agent functionality.
            </p>
            <div className="bg-slate-800/50 border border-slate-700 rounded-md p-4">
              <p className="text-slate-300 text-sm">
                API settings are configured via environment variables:
              </p>
              <ul className="mt-2 text-sm text-slate-400 space-y-1">
                <li><code className="text-blue-400">ANTHROPIC_API_KEY</code> - Your Anthropic API key</li>
                <li><code className="text-blue-400">CLAUDE_CODE_OAUTH_TOKEN</code> - OAuth token from claude setup-token</li>
              </ul>
            </div>
          </div>

          {/* Database */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
            <div className="flex items-center gap-3 mb-4">
              <Database className="h-5 w-5 text-green-400" />
              <h2 className="text-lg font-semibold text-slate-100">Database</h2>
            </div>
            <p className="text-slate-400 text-sm">
              PostgreSQL database connection is configured via <code className="text-blue-400">DATABASE_URL</code> environment variable.
            </p>
          </div>

          {/* Tor Proxy */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
            <div className="flex items-center gap-3 mb-4">
              <Shield className="h-5 w-5 text-purple-400" />
              <h2 className="text-lg font-semibold text-slate-100">Tor Proxy</h2>
            </div>
            <p className="text-slate-400 text-sm">
              Dark web access via Tor SOCKS proxy at <code className="text-blue-400">socks5h://tor:9050</code>
            </p>
          </div>
        </div>

        <div className="mt-8 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
          <p className="text-sm text-blue-300">
            Settings are managed via environment variables in <code>.env</code> file or Docker Compose configuration.
          </p>
        </div>
      </div>
    </div>
  );
}
