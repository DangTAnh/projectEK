import React, { useEffect, useState } from 'react'

export const UI_ICONS = Object.freeze([
  'play-hand',
  'trophy',
  'crown',
  'bomb',
  'skull',
  'blind',
  'nope',
  'peek',
  'pin',
  'trap',
  'dog',
  'defuse',
  'turn',
  'hourglass',
  'swords',
  'sound-on',
  'sound-off',
  'log',
  'link',
  'wrench',
  'sort',
])

export const UI_ICON_MAP = Object.freeze(
  Object.fromEntries(UI_ICONS.map((icon) => [icon, `/ui/${icon}.png`])),
)

const BASE_STYLE = {
  objectFit: 'contain',
  verticalAlign: 'middle',
  display: 'inline-block',
  flexShrink: 0,
  userSelect: 'none',
  WebkitUserDrag: 'none',
  filter: 'drop-shadow(0 1px 2px rgba(0, 0, 0, 0.55))',
}

export default function RealIcon({
  name,
  size = 18,
  alt = '',
  className = '',
  title,
  style,
}) {
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    setFailed(false)
  }, [name])

  if (!name || failed) return null

  const classes = className ? `real-icon ${className}` : 'real-icon'
  const mergedStyle = style
    ? { ...BASE_STYLE, width: size, height: size, ...style }
    : { ...BASE_STYLE, width: size, height: size }

  return (
    <img
      src={`/ui/${name}.png`}
      width={size}
      height={size}
      alt={alt}
      title={title}
      aria-hidden={alt ? undefined : true}
      draggable={false}
      decoding="async"
      className={classes}
      style={mergedStyle}
      onError={() => setFailed(true)}
    />
  )
}
