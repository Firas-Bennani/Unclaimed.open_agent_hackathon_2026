import type { TraceNode } from '../types'
import { fieldLabel, formatValue } from '../lib/format'
import { TriChip } from './ui'

const OP: Record<string, string> = { '>=': '≥', '<=': '≤', '==': '=', '!=': '≠', in: 'in', not_in: 'not in', '<': '<', '>': '>' }
const KIND: Record<string, string> = { all: 'ALL of', any: 'ANY of', not: 'NOT' }

function Leaf({ n }: { n: TraceNode }) {
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <TriChip v={n.result} />
      {n.clause && <span className="rounded bg-navy px-1 font-mono text-[10px] font-bold text-white">{n.clause}</span>}
      <span className="font-semibold text-navy">{fieldLabel(n.subject ?? '')}</span>
      <span className="font-mono text-slate-700">({formatValue(n.left, n.subject)})</span>
      <span className="font-mono font-bold text-slate-500">{OP[n.op ?? ''] ?? n.op}</span>
      <span className="font-mono text-slate-700">{formatValue(n.right)}</span>
    </span>
  )
}

export default function TraceTree({ node, depth = 0 }: { node: TraceNode; depth?: number }) {
  if (node.kind === 'leaf') {
    return (
      <li className="py-0.5 text-xs">
        <Leaf n={node} />
      </li>
    )
  }
  const inner = (
    <>
      <span className="flex items-center gap-1.5 text-xs">
        <TriChip v={node.result} />
        <span className="font-bold uppercase tracking-wide text-slate-600">{KIND[node.kind]}</span>
        {node.clause && <span className="rounded bg-navy px-1 font-mono text-[10px] font-bold text-white">{node.clause}</span>}
      </span>
      <ul className="ml-2 mt-0.5 border-l-2 border-slate-200 pl-3">
        {(node.children ?? []).map((c, i) => (
          <TraceTree key={i} node={c} depth={depth + 1} />
        ))}
      </ul>
    </>
  )
  return depth === 0 ? <ul className="list-none">{<li>{inner}</li>}</ul> : <li className="py-0.5">{inner}</li>
}
