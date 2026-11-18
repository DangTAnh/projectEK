import React from 'react'

export default function PlayerList({ players, turn, phase }) {
  return (
    <div className="players-strip">
      {(players || []).map((p) => (
        <div key={p.name}
             className={`player-chip ${p.alive ? '' : 'dead'} ${phase === 'playing' && turn?.current === p.name ? 'turn' : ''}`}
             title={p.blind ? `${p.name} đang bị mù bài` : p.name}>
          <span className="avatar">{(p.name || '?')[0].toUpperCase()}</span>
          <span className="pname">
            {p.name}{p.blind ? ' 🙈' : ''}{p.extra_turns > 0 ? ` (+${p.extra_turns})` : ''}
          </span>
          <span className="pcount">{p.count} lá</span>
          {(p.faceup?.length || 0) > 0 && <span title="Barking Kitten úp trước mặt">🐶</span>}
          {p.marked && <span title={`Bị Mark: ${p.marked.type}`}>📌</span>}
        </div>
      ))}
    </div>
  )
}
