'use client';

import { Settings, Key, Database, Shield, Brain, CheckCircle, XCircle, RefreshCw } from 'lucide-react';
import { useEffect, useState } from 'react';
import { getModelsInfo, type ModelsInfo } from '@/lib/api';

export default function SettingsPage() {
  const [modelsInfo, setModelsInfo] = useState<ModelsInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadModelsInfo = async () => {
    setLoading(true);
    setError(null);
    try {
      const info = await getModelsInfo();
      setModelsInfo(info);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load model information');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadModelsInfo();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <Settings className="h-8 w-8 text-blue-400" />
          <h1 className="text-2xl font-bold text-slate-100">Settings</h1>
        </div>

        <div className="space-y-6">
          {/* AI Models Section */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <Brain className="h-5 w-5 text-purple-400" />
                <h2 className="text-lg font-semibold text-slate-100">AI Models</h2>
              </div>
              <button
                onClick={loadModelsInfo}
                disabled={loading}
                className="p-2 hover:bg-slate-800 rounded-md transition-colors disabled:opacity-50"
                title="Refresh model information"
              >
                <RefreshCw className={`h-4 w-4 text-slate-400 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
            
            {error && (
              <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-md">
                <p className="text-sm text-red-300">{error}</p>
              </div>
            )}

            {loading && !modelsInfo && (
              <div className="text-center py-8">
                <RefreshCw className="h-8 w-8 text-slate-400 animate-spin mx-auto mb-2" />
                <p className="text-slate-400 text-sm">Loading model information...</p>
              </div>
            )}

            {modelsInfo && (
              <div className="space-y-4">
                {/* Current Model */}
                <div className="bg-slate-800/50 border border-slate-700 rounded-md p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-slate-300">Current Model</span>
                    <span className="text-xs px-2 py-1 bg-blue-500/20 text-blue-300 rounded">
                      {modelsInfo.current_model_type.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-lg font-mono text-slate-100">{modelsInfo.current_model}</p>
                  <p className="text-xs text-slate-400 mt-1">
                    Set via ROBIN_MODEL environment variable
                  </p>
                </div>

                {/* Claude (Anthropic) */}
                <div className="bg-slate-800/50 border border-slate-700 rounded-md p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-100">Claude (Anthropic)</span>
                      {modelsInfo.claude.available ? (
                        <CheckCircle className="h-4 w-4 text-green-400" />
                      ) : (
                        <XCircle className="h-4 w-4 text-red-400" />
                      )}
                    </div>
                    <span className={`text-xs px-2 py-1 rounded ${
                      modelsInfo.claude.available 
                        ? 'bg-green-500/20 text-green-300' 
                        : 'bg-red-500/20 text-red-300'
                    }`}>
                      {modelsInfo.claude.available ? 'Connected' : 'Not configured'}
                    </span>
                  </div>
                  
                  {modelsInfo.claude.available ? (
                    <div className="space-y-2">
                      <p className="text-xs text-slate-400">Available models:</p>
                      <div className="flex flex-wrap gap-2">
                        {modelsInfo.claude.models.map((model) => (
                          <span
                            key={model}
                            className={`text-xs px-2 py-1 rounded font-mono ${
                              model === modelsInfo.current_model
                                ? 'bg-blue-500/30 text-blue-200 border border-blue-500/50'
                                : 'bg-slate-700/50 text-slate-300'
                            }`}
                          >
                            {model}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400">
                      Set <code className="text-blue-400">ANTHROPIC_API_KEY</code> environment variable to enable
                    </p>
                  )}
                </div>

                {/* Ollama */}
                <div className="bg-slate-800/50 border border-slate-700 rounded-md p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-100">Ollama (Local)</span>
                      {modelsInfo.ollama.available ? (
                        <CheckCircle className="h-4 w-4 text-green-400" />
                      ) : (
                        <XCircle className="h-4 w-4 text-red-400" />
                      )}
                    </div>
                    <span className={`text-xs px-2 py-1 rounded ${
                      modelsInfo.ollama.available 
                        ? 'bg-green-500/20 text-green-300' 
                        : 'bg-red-500/20 text-red-300'
                    }`}>
                      {modelsInfo.ollama.available ? 'Connected' : 'Not available'}
                    </span>
                  </div>
                  
                  {modelsInfo.ollama.base_url && (
                    <p className="text-xs text-slate-400 mb-2">
                      Endpoint: <code className="text-blue-400">{modelsInfo.ollama.base_url}</code>
                    </p>
                  )}
                  
                  {modelsInfo.ollama.available ? (
                    <div className="space-y-2">
                      <p className="text-xs text-slate-400">
                        Found {modelsInfo.ollama.models.length} model(s):
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {modelsInfo.ollama.models.map((model) => (
                          <span
                            key={model}
                            className={`text-xs px-2 py-1 rounded font-mono ${
                              model === modelsInfo.current_model
                                ? 'bg-blue-500/30 text-blue-200 border border-blue-500/50'
                                : 'bg-slate-700/50 text-slate-300'
                            }`}
                          >
                            {model}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400">
                      Install and run Ollama to use local models. See{' '}
                      <a 
                        href="https://ollama.ai" 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-blue-400 hover:underline"
                      >
                        ollama.ai
                      </a>
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

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
