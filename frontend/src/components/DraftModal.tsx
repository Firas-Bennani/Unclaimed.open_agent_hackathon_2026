import { marked } from 'marked'
import { useState } from 'react'
import { api } from '../api'
import { useAsync } from '../lib/useAsync'
import { BENEFIT_LONG } from '../lib/format'
import { Button, ErrorBox, Modal, Spinner } from './ui'

export default function DraftModal({ householdId, benefit, onClose }: { householdId: string; benefit: string; onClose: () => void }) {
  const draft = useAsync(() => api.draft(householdId, benefit), [householdId, benefit])
  const [copied, setCopied] = useState(false)

  const download = () => {
    if (!draft.data) return
    const blob = new Blob([draft.data.markdown], { type: 'text/markdown' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${householdId}-${benefit}-draft.md`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <Modal title={`Draft application: ${BENEFIT_LONG[benefit] ?? benefit}`} onClose={onClose} wide>
      {draft.loading && <Spinner label="Preparing draft…" />}
      {draft.error && <ErrorBox error={draft.error} onRetry={draft.reload} />}
      {draft.data && (
        <>
          <div className="mb-3 flex gap-2">
            <Button
              variant="secondary"
              onClick={async () => {
                await navigator.clipboard.writeText(draft.data!.markdown)
                setCopied(true)
              }}
            >
              {copied ? 'Copied ✓' : 'Copy markdown'}
            </Button>
            <Button variant="secondary" onClick={download}>
              Download .md
            </Button>
          </div>
          <article
            className="draft max-h-[65vh] overflow-y-auto rounded-lg border border-slate-200 p-4 text-sm"
            dangerouslySetInnerHTML={{ __html: marked.parse(draft.data.markdown, { async: false }) as string }}
          />
        </>
      )}
    </Modal>
  )
}
