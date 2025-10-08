import { useEffect, useMemo, useState } from 'react'

type Pipeline = {
  name: string
  path: string
  description?: string
  inputs?: Record<string, string>
}

type RunResult = {
  run_id: string
  artifacts_path: string
  steps: Array<{ id: string; type: string; outputs: Record<string, unknown> }>
}

const initialMessage = 'Select a pipeline to preview its inputs and run the local PoC.'

export default function App() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([])
  const [selectedName, setSelectedName] = useState<string>('')
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [status, setStatus] = useState<string>(initialMessage)
  const [isRunning, setIsRunning] = useState(false)
  const [lastRun, setLastRun] = useState<RunResult | null>(null)

  useEffect(() => {
    fetch('/api/pipelines')
      .then((res) => res.json())
      .then((data: Pipeline[]) => {
        setPipelines(data)
        if (data.length > 0) {
          setSelectedName(data[0].name)
        }
      })
      .catch((error) => {
        console.error(error)
        setStatus('Failed to load pipelines. Is the API running on :8000?')
      })
  }, [])

  const selectedPipeline = useMemo(
    () => pipelines.find((p) => p.name === selectedName) ?? null,
    [pipelines, selectedName]
  )

  useEffect(() => {
    if (!selectedPipeline) {
      return
    }
    const defaults: Record<string, string> = {}
    Object.keys(selectedPipeline.inputs ?? {}).forEach((key) => {
      defaults[key] = inputs[key] ?? ''
    })
    setInputs(defaults)
    setStatus(initialMessage)
    setLastRun(null)
  }, [selectedPipeline])

  const updateInput = (key: string, value: string) => {
    setInputs((prev) => ({ ...prev, [key]: value }))
  }

  const handleRun = async () => {
    if (!selectedPipeline) return
    setIsRunning(true)
    setStatus('Running pipeline...')
    try {
      const response = await fetch('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pipeline: selectedPipeline.name, inputs })
      })
      if (!response.ok) {
        throw new Error(await response.text())
      }
      const data: RunResult = await response.json()
      setLastRun(data)
      setStatus(`Run complete! Artifacts saved to ${data.artifacts_path}`)
    } catch (error) {
      console.error(error)
      setStatus('Run failed. Check the API logs for details.')
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <div
      style={{
        width: 'min(960px, 100%)',
        background: '#ffffffee',
        borderRadius: '24px',
        padding: '2.5rem',
        boxShadow: '0 20px 60px rgba(15, 23, 42, 0.15)'
      }}
    >
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ margin: 0 }}>Agent Pipeline Studio</h1>
          <p style={{ marginTop: '0.5rem', maxWidth: '640px' }}>
            Prototype GUI for the local-first agent orchestrator. Pick a pipeline, fill in the
            prompt inputs, and launch a run via the FastAPI backend.
          </p>
        </div>
      </header>

      <section style={{ display: 'grid', gap: '2rem', marginTop: '2rem', gridTemplateColumns: '1fr 1fr' }}>
        <div>
          <h2>Available Pipelines</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {pipelines.map((pipeline) => (
              <button
                key={pipeline.name}
                onClick={() => setSelectedName(pipeline.name)}
                style={{
                  textAlign: 'left',
                  padding: '1rem',
                  borderRadius: '16px',
                  border: selectedName === pipeline.name ? '2px solid #2563eb' : '1px solid #cbd5f5',
                  background: selectedName === pipeline.name ? '#dbeafe' : '#f1f5f9',
                  transition: 'all 0.2s ease'
                }}
              >
                <strong>{pipeline.name}</strong>
                {pipeline.description && <p style={{ marginTop: '0.5rem' }}>{pipeline.description}</p>}
              </button>
            ))}
          </div>
        </div>

        <div>
          <h2>Inputs</h2>
          {!selectedPipeline && <p>No pipeline selected.</p>}
          {selectedPipeline && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {Object.keys(selectedPipeline.inputs ?? {}).map((key) => (
                <label key={key} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <span style={{ fontWeight: 600 }}>{key}</span>
                  <input
                    value={inputs[key] ?? ''}
                    onChange={(event) => updateInput(key, event.target.value)}
                    placeholder={`Enter ${key}`}
                    style={{
                      padding: '0.75rem 1rem',
                      borderRadius: '12px',
                      border: '1px solid #cbd5f5',
                      fontSize: '1rem'
                    }}
                  />
                </label>
              ))}
              <button
                onClick={handleRun}
                disabled={isRunning}
                style={{
                  marginTop: '1rem',
                  padding: '0.9rem 1.2rem',
                  borderRadius: '999px',
                  border: 'none',
                  background: isRunning ? '#94a3b8' : '#2563eb',
                  color: '#fff',
                  fontWeight: 600,
                  fontSize: '1rem'
                }}
              >
                {isRunning ? 'Running…' : 'Run Pipeline'}
              </button>
            </div>
          )}
        </div>
      </section>

      <section style={{ marginTop: '2.5rem' }}>
        <h2>Status</h2>
        <p>{status}</p>
        {lastRun && (
          <div style={{ marginTop: '1rem', padding: '1.5rem', borderRadius: '16px', background: '#f8fafc' }}>
            <h3 style={{ marginTop: 0 }}>Last Run Outputs</h3>
            <p>
              <strong>Run ID:</strong> {lastRun.run_id}
            </p>
            <p>
              <strong>Artifacts:</strong> {lastRun.artifacts_path}
            </p>
            <ul>
              {lastRun.steps.map((step) => (
                <li key={step.id}>
                  <strong>{step.id}</strong>: {Object.keys(step.outputs).join(', ')}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  )
}
