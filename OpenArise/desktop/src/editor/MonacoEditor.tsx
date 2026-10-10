import 'monaco-editor/editor/contrib/find/browser/findController.js';
import 'monaco-editor/editor/contrib/folding/browser/folding.js';
import 'monaco-editor/editor/standalone/browser/quickAccess/standaloneGotoLineQuickAccess.js';
import { useEffect, useRef } from 'react';
import * as monaco from 'monaco-editor/editor/editor.api.js';
import 'monaco-editor/languages/definitions/python/register.js';
import 'monaco-editor/languages/definitions/typescript/register.js';
import 'monaco-editor/languages/definitions/javascript/register.js';
import 'monaco-editor/languages/features/json/register.js';
import 'monaco-editor/languages/definitions/html/register.js';
import 'monaco-editor/languages/definitions/css/register.js';
import 'monaco-editor/languages/definitions/markdown/register.js';
import 'monaco-editor/languages/definitions/yaml/register.js';
import 'monaco-editor/languages/definitions/ini/register.js';
import 'monaco-editor/languages/definitions/xml/register.js';
import { editorLanguage } from './language';
import EditorWorker from 'monaco-editor/editor/editor.worker.js?worker&inline';
import JsonWorker from 'monaco-editor/languages/features/json/json.worker.js?worker&inline';
import type { EditorTab } from '../workspace/useWorkspace';

// Local bundled worker: no CDN, remote script, Node integration or webSecurity changes.
self.MonacoEnvironment = { getWorker: (_module, label) => label === 'json' ? new JsonWorker() : new EditorWorker() };
monaco.editor.defineTheme('openarise', {
  base: 'vs-dark', inherit: true,
  rules: [
    { token: 'keyword', foreground: 'BD93F9' }, { token: 'string', foreground: 'A5D9A6' },
    { token: 'number', foreground: 'E8BC7D' }, { token: 'comment', foreground: '687C9B', fontStyle: 'italic' },
  ],
  colors: {
    'editor.background': '#080E1C', 'editor.foreground': '#CFD9EC',
    'editorLineNumber.foreground': '#485A79', 'editorLineNumber.activeForeground': '#91BFFF',
    'editorCursor.foreground': '#5DCFFF', 'editor.selectionBackground': '#28497888',
    'editor.lineHighlightBackground': '#101C30', 'editorWidget.background': '#111D31',
    'minimap.background': '#080E1C', 'editorGutter.background': '#080E1C',
    'scrollbarSlider.background': '#32456366',
  },
});
export default function MonacoEditor({ tabs, active, onChange, onSave, locked = false }: {
  tabs: EditorTab[]; active: string; onChange: (path: string, content: string) => void; onSave: (path: string) => void; locked?: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);
  const instance = useRef<monaco.editor.IStandaloneCodeEditor | undefined>(undefined);
  const models = useRef(new Map<string, monaco.editor.ITextModel>());
  const views = useRef(new Map<string, monaco.editor.ICodeEditorViewState>());
  const previous = useRef('');
  const synchronizing = useRef(false);
  const callbacks = useRef({ onChange, onSave, active });
  callbacks.current = { onChange, onSave, active };
  useEffect(() => {
    if (!container.current) return;
    const editor = monaco.editor.create(container.current, {
      theme: 'openarise', editContext: false, model: null, automaticLayout: true, minimap: { enabled: true },
      fontFamily: "'Cascadia Code', Consolas, monospace", fontSize: 13, lineHeight: 23,
      lineNumbers: 'on', padding: { top: 18 }, scrollBeyondLastLine: false,
      smoothScrolling: false, renderLineHighlight: 'all', ariaLabel: 'Code editor',
    });
    instance.current = editor;
    const change = editor.onDidChangeModelContent(() => {
      if (synchronizing.current) return;
      const model = editor.getModel();
      const entry = [...models.current].find(([, value]) => value === model);
      if (entry && model) callbacks.current.onChange(entry[0], model.getValue());
    });
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => callbacks.current.onSave(callbacks.current.active));
    return () => {
      change.dispose(); editor.dispose(); instance.current = undefined;
      for (const model of models.current.values()) model.dispose();
      models.current.clear(); views.current.clear(); previous.current = '';
    };
  }, []);
  useEffect(() => {
    const editor = instance.current;
    if (!editor) return;
    for (const [path, model] of models.current) {
      if (!tabs.some(t => t.path === path)) {
        if (editor.getModel() === model) editor.setModel(null);
        model.dispose(); models.current.delete(path); views.current.delete(path);
      }
    }
    const tab = tabs.find(t => t.path === active);
    if (!tab) { editor.setModel(null); return; }
    let model = models.current.get(active);
    if (!model) {
      model = monaco.editor.createModel(tab.content, editorLanguage(active));
      // File reads normalize text to LF. Empty/single-line models otherwise
      // inherit Windows CRLF, forcing a full model reset on their first save.
      model.setEOL(monaco.editor.EndOfLineSequence.LF);
      models.current.set(active, model);
    }
    if (model.getValue() !== tab.content) {
      synchronizing.current = true;
      try { model.setValue(tab.content); } finally { synchronizing.current = false; }
    }
    if (editor.getModel() !== model) {
      const view = editor.saveViewState();
      if (view && previous.current) views.current.set(previous.current, view);
      editor.setModel(model);
      const saved = views.current.get(active); if (saved) editor.restoreViewState(saved);
      previous.current = active; editor.focus();
    }
    editor.updateOptions({ readOnly: tab.readOnly || locked });
  }, [tabs, active, locked]);
  return <div className="monaco-surface" ref={container} data-testid="monaco-editor" />;
}
