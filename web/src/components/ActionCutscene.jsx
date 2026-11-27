import React, { useEffect, useState } from 'react'
import './ActionCutscene.css'

export const FX_PRELOAD_IMAGES = [
  '/ui/fx/businessman-run.png',
  '/ui/fx/draw-hand.png',
  '/ui/fx/shuffle-hands.png',
  '/ui/fx/reverse-sign.png',
  '/ui/fx/nope-man.png',
  '/ui/fx/shovel.png',
  '/ui/fx/zombie-hand.png',
  '/ui/fx/steal-hand.png',
  '/ui/fx/future-eyes.png',
  '/ui/fx/attack-fist.png',
  '/static/cards/barkingkitten/0.jpg',
  '/static/cards/clone/0.jpg',
  '/static/cards/cat/0.jpg',
  '/static/cards/feralcat/0.jpg',
  '/static/cards/implodingkitten/0.jpg',
  '/static/cards/skip/0.jpg',
]

export function getActionDuration(fx) {
  const ct = fx?.card_type || fx?.cardType
  if (ct === 'barkingkitten') return 1780
  if (ct === 'imploding_arm') return 1680
  if (ct === 'clone') return 1480
  if (ct === 'combo_pair' || ct === 'combo_three') return 1440
  return 1350
}

function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function CutsceneImg({ src, fallback, className = '', resetKey }) {
  const [stage, setStage] = useState(0)

  useEffect(() => {
    setStage(0)
  }, [src, fallback, resetKey])

  const activeSrc = stage === 0 ? src : stage === 1 ? fallback : null
  if (!activeSrc) return null

  return (
    <img
      src={activeSrc}
      alt=""
      className={className}
      draggable={false}
      decoding="async"
      onError={() => {
        setStage((prev) => {
          if (prev === 0 && fallback && fallback !== src) return 1
          return 2
        })
      }}
    />
  )
}

export function resolveActionPreset(fxEvent) {
  if (!fxEvent || typeof fxEvent !== 'object') return null

  const { kind, card_type: cardType, actor, target, count, source } = fxEvent

  if (kind === 'draw' || kind === 'transfer' || kind === 'put_deck' || kind === 'receive') {
    return null
  }

  if (kind === 'nope') {
    const isYup = typeof count === 'number' && count > 0 && count % 2 === 0
    return {
      family: 'nope',
      tone: isYup ? 'emerald' : 'danger',
      stamp: isYup ? 'YUP! COUNTER-NOPE!' : 'NOPE!',
      primaryImg: '/ui/fx/nope-man.png',
      primaryFallback: '/ui/nope.png',
      badgeImg: '/ui/nope.png',
      badgeFallback: '/ui/nope.png',
      actor,
      target,
      count,
      cardType: 'nope',
      isYup,
    }
  }

  if (kind === 'defuse') {
    let stamp = 'DEFUSED!'
    if (cardType === 'streakingkitten') stamp = 'STREAKING SAVE!'
    else if (cardType === 'zombiekitten') stamp = 'ZOMBIE RESCUE!'
    else if (cardType === 'godcat') stamp = 'GODCAT DEFUSE!'
    return {
      family: 'defuse',
      tone: 'emerald',
      stamp,
      primaryImg: '/ui/defuse.png',
      primaryFallback: '/ui/wrench.png',
      secondaryImg: '/ui/bomb.png',
      secondaryFallback: '/ui/skull.png',
      actor,
      target,
      count,
      cardType: cardType || 'defuse',
    }
  }

  if (kind && kind !== 'card_fx') return null

  switch (cardType) {
    case 'skip':
    case 'superskip':
      return {
        family: 'skip',
        tone: cardType === 'superskip' ? 'gold' : 'emerald',
        stamp: cardType === 'superskip' ? 'SUPER SKIP!' : 'SKIP!',
        primaryImg: '/ui/fx/businessman-run.png',
        primaryFallback: '/ui/turn.png',
        actor,
        target,
        count,
        cardType,
      }

    case 'attack2x':
    case 'targetattack2x':
    case 'personalattack3x':
    case 'attackofthedead': {
      const stampMap = {
        attack2x: 'ATTACK ×2!',
        targetattack2x: 'TARGETED ATTACK!',
        personalattack3x: 'PERSONAL ATTACK ×3!',
        attackofthedead: 'ATTACK OF THE DEAD!',
      }
      return {
        family: 'attack',
        tone: 'danger',
        stamp: stampMap[cardType],
        primaryImg: '/ui/fx/attack-fist.png',
        primaryFallback: '/ui/swords.png',
        actor,
        target,
        count,
        cardType,
      }
    }

    case 'reverse':
      return {
        family: 'reverse',
        tone: 'emerald',
        stamp: 'REVERSE!',
        primaryImg: '/ui/fx/reverse-sign.png',
        primaryFallback: '/ui/turn.png',
        actor,
        target,
        count,
        cardType,
      }

    case 'shuffle':
    case 'shufflenow':
      return {
        family: 'shuffle',
        tone: 'gold',
        stamp: cardType === 'shufflenow' ? 'SHUFFLE NOW!' : 'SHUFFLE!',
        primaryImg: '/ui/fx/shuffle-hands.png',
        primaryFallback: '/ui/sort.png',
        actor,
        target,
        count,
        cardType,
      }

    case 'seethefuture3x':
    case 'seethefuture5x':
    case 'revealthefuture3x':
    case 'sharethefuture3x':
    case 'alter3x':
    case 'alter5x':
    case 'alter3xnow':
    case 'clairvoyance': {
      const stampMap = {
        alter3x: 'ALTER THE FUTURE!',
        alter5x: 'ALTER THE FUTURE!',
        alter3xnow: 'ALTER THE FUTURE!',
        revealthefuture3x: 'REVEAL THE FUTURE!',
        sharethefuture3x: 'SHARE THE FUTURE!',
        clairvoyance: 'CLAIRVOYANCE!',
        seethefuture3x: 'SEE THE FUTURE!',
        seethefuture5x: 'SEE THE FUTURE!',
      }
      return {
        family: 'future',
        tone: 'gold',
        stamp: stampMap[cardType],
        primaryImg: '/ui/fx/future-eyes.png',
        primaryFallback: '/ui/peek.png',
        actor,
        target,
        count,
        cardType,
      }
    }

    case 'favor':
      return {
        family: 'favor',
        tone: 'gold',
        stamp: 'FAVOR!',
        primaryImg: '/handout.png',
        primaryFallback: '/ui/trap.png',
        actor,
        target,
        count,
        cardType,
        subText: 'DEMANDS A CARD',
      }

    case 'steal':
    case 'three':
    case 'illtakethat': {
      const stampMap = {
        illtakethat: "I'LL TAKE THAT!",
        steal: 'STEAL!',
        three: 'TRIPLE STEAL!',
      }
      return {
        family: 'steal',
        tone: 'gold',
        stamp: stampMap[cardType],
        primaryImg: '/ui/fx/steal-hand.png',
        primaryFallback: '/handout.png',
        secondaryImg: '/backside.jpg',
        secondaryFallback: '/ui/sort.png',
        actor,
        target,
        count,
        cardType,
      }
    }

    case 'clone':
      return {
        family: 'clone',
        tone: 'cyan',
        stamp: 'CLONE!',
        primaryImg: '/static/cards/clone/0.jpg',
        primaryFallback: '/ui/sort.png',
        secondaryImg: source ? `/static/cards/${source}/0.jpg` : '/backside.jpg',
        secondaryFallback: '/backside.jpg',
        actor,
        target,
        count,
        cardType,
        subText: source ? `CLONED ${source.toUpperCase()}` : 'MIRROR COPY',
      }

    case 'combo_pair':
    case 'combo_three': {
      const comboCount = cardType === 'combo_three' ? 3 : 2
      return {
        family: 'combo',
        tone: 'gold',
        stamp: cardType === 'combo_three' ? 'TRIPLE COMBO!' : 'PAIR COMBO!',
        primaryImg: '/ui/fx/steal-hand.png',
        primaryFallback: '/handout.png',
        comboCardImg: source ? `/static/cards/${source}/0.jpg` : '/static/cards/cat/0.jpg',
        comboFallback: '/backside.jpg',
        comboCount,
        actor,
        target,
        count: comboCount,
        cardType,
        subText: cardType === 'combo_three' ? 'CALL A CARD' : 'BLIND STEAL',
      }
    }

    case 'imploding_arm':
      return {
        family: 'imploding_arm',
        tone: 'cosmic',
        stamp: 'IMPLODING ARMED!',
        primaryImg: '/static/cards/implodingkitten/0.jpg',
        primaryFallback: '/ui/bomb.png',
        secondaryImg: '/backside.jpg',
        secondaryFallback: '/ui/bomb.png',
        actor,
        target,
        count,
        cardType,
        subText: 'FACE UP · UNDEFUSABLE!',
      }

    case 'curseofthecatbutt':
      return {
        family: 'blind',
        tone: 'danger',
        stamp: 'CURSED BLIND!',
        primaryImg: '/ui/blind.png',
        primaryFallback: '/ui/nope.png',
        actor,
        target,
        count,
        cardType,
      }

    case 'mark':
      return {
        family: 'mark',
        tone: 'gold',
        stamp: 'MARKED!',
        primaryImg: '/ui/pin.png',
        primaryFallback: '/ui/trap.png',
        secondaryImg: '/backside.jpg',
        secondaryFallback: '/ui/sort.png',
        actor,
        target,
        count,
        cardType,
      }

    case 'digdeeper':
    case 'raisingheck':
    case 'bury':
    case 'swaptopandbottom': {
      const stampMap = {
        digdeeper: 'DIG DEEPER!',
        raisingheck: 'RAISING HECK!',
        bury: 'BURY!',
        swaptopandbottom: 'SWAP TOP ↔ BOTTOM!',
      }
      return {
        family: 'dig',
        tone: 'gold',
        stamp: stampMap[cardType],
        primaryImg: '/ui/fx/shovel.png',
        primaryFallback: '/ui/wrench.png',
        secondaryImg: '/backside.jpg',
        secondaryFallback: '/ui/sort.png',
        actor,
        target,
        count,
        cardType,
      }
    }

    case 'towerofpower':
      return {
        family: 'tower',
        tone: 'gold',
        stamp: 'TOWER OF POWER!',
        primaryImg: '/ui/crown.png',
        primaryFallback: '/ui/trophy.png',
        actor,
        target,
        count,
        cardType,
      }

    case 'zombiekitten':
    case 'feedthedead':
      return {
        family: 'zombie',
        tone: 'lime',
        stamp: cardType === 'feedthedead' ? 'FEED THE DEAD!' : 'REVIVED!',
        primaryImg: '/ui/fx/zombie-hand.png',
        primaryFallback: '/ui/skull.png',
        actor,
        target,
        count,
        cardType,
      }

    case 'barkingkitten':
      return {
        family: 'barking',
        tone: 'danger',
        stamp: 'BARKING KITTEN!',
        introCardImg: '/static/cards/barkingkitten/0.jpg',
        introFallback: '/ui/dog.png',
        primaryImg: '/ui/dog.png',
        primaryFallback: '/ui/swords.png',
        actor,
        target,
        count,
        cardType,
      }

    case 'potluck':
    case 'garbagecollection':
    case 'graverobber': {
      const stampMap = {
        potluck: 'POTLUCK!',
        garbagecollection: 'GARBAGE COLLECTION!',
        graverobber: 'GRAVE ROBBER!',
      }
      return {
        family: 'potluck',
        tone: 'gold',
        stamp: stampMap[cardType],
        primaryImg: '/backside.jpg',
        primaryFallback: '/ui/sort.png',
        actor,
        target,
        count,
        cardType,
      }
    }

    case 'catomicbomb':
    case 'armageddon':
      return {
        family: 'catomic',
        tone: 'danger',
        stamp: cardType === 'armageddon' ? 'ARMAGEDDON!' : 'CATOMIC BOMB!',
        primaryImg: '/ui/bomb.png',
        primaryFallback: '/ui/skull.png',
        actor,
        target,
        count,
        cardType,
      }

    default:
      return null
  }
}

export const ACTION_FX_PRESETS = [
  { id: 'skip', label: 'Skip — Businessman Run', fx: { kind: 'card_fx', card_type: 'skip', actor: 'Alice' } },
  { id: 'superskip', label: 'Super Skip', fx: { kind: 'card_fx', card_type: 'superskip', actor: 'Alice' } },
  { id: 'attack2x', label: 'Attack ×2', fx: { kind: 'card_fx', card_type: 'attack2x', actor: 'Alice' } },
  { id: 'reverse', label: 'Reverse', fx: { kind: 'card_fx', card_type: 'reverse', actor: 'Bob' } },
  { id: 'shuffle', label: 'Shuffle', fx: { kind: 'card_fx', card_type: 'shuffle', actor: 'Charlie' } },
  { id: 'nope', label: 'Nope', fx: { kind: 'nope', actor: 'Diana', count: 1 } },
  { id: 'yup', label: 'Yup', fx: { kind: 'nope', actor: 'Alice', count: 2 } },
  { id: 'defuse', label: 'Defuse', fx: { kind: 'defuse', card_type: 'defuse', actor: 'Alice' } },
  { id: 'seefuture', label: 'See Future', fx: { kind: 'card_fx', card_type: 'seethefuture3x', actor: 'Bob' } },
  { id: 'steal', label: 'Steal', fx: { kind: 'card_fx', card_type: 'illtakethat', actor: 'Charlie', target: 'Diana' } },
  { id: 'blind', label: 'Curse Blind', fx: { kind: 'card_fx', card_type: 'curseofthecatbutt', actor: 'Alice', target: 'Bob' } },
  { id: 'mark', label: 'Mark', fx: { kind: 'card_fx', card_type: 'mark', actor: 'Charlie', target: 'Alice' } },
  { id: 'dig', label: 'Dig / Bury', fx: { kind: 'card_fx', card_type: 'digdeeper', actor: 'Diana' } },
  { id: 'zombie', label: 'Zombie', fx: { kind: 'card_fx', card_type: 'zombiekitten', actor: 'Bob', target: 'Charlie' } },
  { id: 'barking', label: 'Barking', fx: { kind: 'card_fx', card_type: 'barkingkitten', actor: 'Diana' } },
  { id: 'potluck', label: 'Potluck', fx: { kind: 'card_fx', card_type: 'potluck', actor: 'Alice' } },
  { id: 'clone', label: 'Clone', fx: { kind: 'card_fx', card_type: 'clone', source: 'skip', actor: 'Alice' } },
  { id: 'combo_pair', label: 'Pair Combo', fx: { kind: 'card_fx', card_type: 'combo_pair', source: 'cat', actor: 'Bob', count: 2 } },
  { id: 'combo_three', label: 'Triple Combo', fx: { kind: 'card_fx', card_type: 'combo_three', source: 'feralcat', actor: 'Charlie', count: 3 } },
  { id: 'imploding_arm', label: 'Imploding Armed', fx: { kind: 'card_fx', card_type: 'imploding_arm', actor: 'Diana' } },
  { id: 'favor', label: 'Favor Call', fx: { kind: 'card_fx', card_type: 'favor', actor: 'Alice' } },
]

function formatSubline(preset) {
  if (preset.actor && preset.target) return `${preset.actor} → ${preset.target}`
  if (preset.actor && preset.subText) return `${preset.actor} · ${preset.subText}`
  if (preset.actor) return preset.actor
  return preset.subText || null
}

export default React.memo(function ActionCutscene({ fx }) {
  if (!fx || prefersReducedMotion()) return null

  const preset = resolveActionPreset(fx)
  if (!preset) return null

  const key = fx.key || `${preset.family}:${preset.cardType}:${preset.count || 0}`
  const subline = formatSubline(preset)
  const rootClass = [
    'action-cutscene-layer',
    `ac-family-${preset.family}`,
    `ac-tone-${preset.tone}`,
    preset.cardType ? `ac-card-${preset.cardType}` : '',
    preset.isYup ? 'is-yup' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div key={key} className={rootClass} aria-hidden="true">
      <div className="ac-backdrop" />
      <div className="ac-ring ac-ring-a" />
      <div className="ac-ring ac-ring-b" />

      {preset.family === 'skip' && (
        <div className="ac-speed-lines">
          <span className="ac-streak s1" />
          <span className="ac-streak s2" />
          <span className="ac-streak s3" />
          <span className="ac-streak s4" />
        </div>
      )}

      {preset.family === 'shuffle' && (
        <div className="ac-card-fan">
          <div className="ac-fan-card f1">
            <CutsceneImg src="/backside.jpg" fallback="/ui/sort.png" className="ac-card-img" resetKey={key} />
          </div>
          <div className="ac-fan-card f2">
            <CutsceneImg src="/backside.jpg" fallback="/ui/sort.png" className="ac-card-img" resetKey={key} />
          </div>
          <div className="ac-fan-card f3">
            <CutsceneImg src="/backside.jpg" fallback="/ui/sort.png" className="ac-card-img" resetKey={key} />
          </div>
        </div>
      )}

      {preset.family === 'potluck' && (
        <div className="ac-swirl-cards">
          <div className="ac-swirl-card c1">
            <CutsceneImg src="/backside.jpg" fallback="/ui/sort.png" className="ac-card-img" resetKey={key} />
          </div>
          <div className="ac-swirl-card c2">
            <CutsceneImg src="/backside.jpg" fallback="/ui/sort.png" className="ac-card-img" resetKey={key} />
          </div>
          <div className="ac-swirl-card c3">
            <CutsceneImg src="/backside.jpg" fallback="/ui/sort.png" className="ac-card-img" resetKey={key} />
          </div>
        </div>
      )}

      {preset.family === 'combo' && (
        <div className={`ac-combo-fan is-count-${preset.comboCount || 2}`}>
          <div className="ac-combo-card cc1">
            <CutsceneImg src={preset.comboCardImg} fallback={preset.comboFallback} className="ac-card-img" resetKey={key} />
          </div>
          <div className="ac-combo-card cc2">
            <CutsceneImg src={preset.comboCardImg} fallback={preset.comboFallback} className="ac-card-img" resetKey={key} />
          </div>
          {preset.comboCount === 3 && (
            <div className="ac-combo-card cc3">
              <CutsceneImg src={preset.comboCardImg} fallback={preset.comboFallback} className="ac-card-img" resetKey={key} />
            </div>
          )}
        </div>
      )}

      {preset.family === 'clone' && <div className="ac-clone-beam" />}

      {preset.introCardImg && (
        <div className="ac-intro-card">
          <CutsceneImg
            src={preset.introCardImg}
            fallback={preset.introFallback || preset.primaryImg}
            className="ac-intro-card-img"
            resetKey={key}
          />
        </div>
      )}

      {preset.secondaryImg && (
        <div
          className={`ac-secondary-prop ${
            preset.family === 'defuse'
              ? 'is-prop-icon'
              : preset.family === 'imploding_arm'
                ? 'is-prop-flipback'
                : 'is-prop-card'
          }`}
        >
          <CutsceneImg
            src={preset.secondaryImg}
            fallback={preset.secondaryFallback}
            className="ac-prop-img"
            resetKey={key}
          />
        </div>
      )}

      {preset.family !== 'potluck' && (
        <div className="ac-hero-track">
          <div className="ac-hero-orient">
            <CutsceneImg
              src={preset.primaryImg}
              fallback={preset.primaryFallback}
              className="ac-hero-img"
              resetKey={key}
            />
          </div>
        </div>
      )}

      {preset.family === 'nope' && (
        <div className="ac-nope-badge">
          <CutsceneImg
            src={preset.badgeImg}
            fallback={preset.badgeFallback}
            className="ac-nope-badge-img"
            resetKey={key}
          />
        </div>
      )}

      <div className="ac-banner">
        <div className="ac-stamp">{preset.stamp}</div>
        {subline && <div className="ac-subline">{subline}</div>}
      </div>
    </div>
  )
})
