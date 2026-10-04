import 'monaco-editor/editor/contrib/find/browser/findController.js';
import 'monaco-editor/editor/contrib/folding/browser/folding.js';
import 'monaco-editor/editor/standalone/browser/quickAccess/standaloneGotoLineQuickAccess.js';
import { useEffect, useRef } from 'react';
import * as monaco from 'monaco-editor/editor/editor.api.js';
import 'monaco-editor/languages/definitions/python/register.js';
import EditorWorker from 'monaco-editor/editor/editor.worker.js?worker&inline';
import type { EditorTab } from '../workspace/useWorkspace';

// Local bundled worker: no CDN, remote script, Node integration or webSecurity changes.
self.MonacoEnvironment = { getWorker: () => new EditorWorker() };
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
export default function MonacoEditor({ tabs, active, onChange, onSave }: {
  tabs: EditorTab[]; active: string; onChange: (path: string, content: string) => void; onSave: (path: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const instance = useRef<monaco.editor.IStandaloneCodeEditor | undefined>(undefined);
  const models = useRef(new Map<string, monaco.editor.ITextModel>());
  const views = useRef(new Map<string, monaco.editor.ICodeEditorViewState>());
  const previous = useRef('');
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
      model = monaco.editor.createModel(tab.content, /\.pyw?$/i.test(active) ? 'python' : 'plaintext');
      models.current.set(active, model);
    }
    if (editor.getModel() !== model) {
      const view = editor.saveViewState();
      if (view && previous.current) views.current.set(previous.current, view);
      editor.setModel(model);
      const saved = views.current.get(active); if (saved) editor.restoreViewState(saved);
      previous.current = active; editor.focus();
    }
    editor.updateOptions({ readOnly: tab.readOnly });
  }, [tabs, active]);
  return <div className="monaco-surface" ref={container} data-testid="monaco-editor" />;
}
