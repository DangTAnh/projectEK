import React, { useId } from 'react'
import { FUR_MAP, normalizeAvatar } from '../utils/catAvatar.js'

const INK = '#181210'

/* Back layer for wrap-around hats (In-Bread Toast & Cone of Shame) */
function CatHatBack({ hat }) {
  if (hat === 'toast') {
    return (
      <g>
        <path
          d="M14 26 C10 10 26 2 58 2 C90 2 106 10 102 26 L104 86 C104 91 98 94 90 94 L26 94 C18 94 12 91 12 86 Z"
          fill="#c47a32"
          stroke={INK}
          strokeWidth="3.6"
          strokeLinejoin="round"
        />
        <path
          d="M20 28 C18 15 30 9 58 9 C86 9 98 15 96 28 L97 82 C97 86 93 88 86 88 L30 88 C23 88 19 86 19 82 Z"
          fill="#f2d399"
          stroke="#9e5e20"
          strokeWidth="2"
        />
        <circle cx="28" cy="24" r="2.2" fill="#d9b26f" />
        <circle cx="88" cy="26" r="2.6" fill="#d9b26f" />
        <circle cx="86" cy="74" r="2.1" fill="#d9b26f" />
        <circle cx="28" cy="76" r="2" fill="#d9b26f" />
      </g>
    )
  }
  if (hat === 'cone') {
    return (
      <g>
        <path
          d="M2 24 C18 4 98 4 114 24 L92 84 C74 90 42 90 24 84 Z"
          fill="rgba(218, 240, 255, 0.42)"
          stroke={INK}
          strokeWidth="3.2"
          strokeLinejoin="round"
        />
        <path
          d="M7 28 C28 14 88 14 109 28"
          fill="none"
          stroke="rgba(255,255,255,0.65)"
          strokeWidth="2.4"
          strokeLinecap="round"
        />
        <path d="M18 38 L28 74 M98 38 L88 74" stroke="rgba(24,18,16,0.28)" strokeWidth="1.8" strokeDasharray="4 4" />
      </g>
    )
  }
  return null
}

function CatFurDetails({ furId, fur }) {
  if (furId === 'potato') {
    return (
      <g>
        <ellipse cx="35" cy="36" rx="6.5" ry="4" fill={fur.shade} opacity="0.55" />
        <ellipse cx="79" cy="64" rx="8" ry="5" fill={fur.shade} opacity="0.5" />
        <circle cx="67" cy="34" r="3" fill={fur.stripe} opacity="0.55" />
        <circle cx="32" cy="68" r="2.8" fill={fur.stripe} opacity="0.5" />
        <circle cx="82" cy="40" r="2.2" fill={fur.stripe} opacity="0.55" />
      </g>
    )
  }
  if (furId === 'sphynx') {
    return (
      <g fill="none" stroke={fur.stripe} strokeWidth="2.2" strokeLinecap="round" opacity="0.72">
        <path d="M44 33 Q58 37 72 33" />
        <path d="M48 38 Q58 41 68 38" />
        <path d="M27 65 Q34 69 38 66" />
        <path d="M89 65 Q82 69 78 66" />
        <path d="M44 76 Q58 81 72 76" />
      </g>
    )
  }
  return null
}

function CatPattern({ pattern, fur }) {
  if (pattern === 'tabby') {
    return (
      <g fill="none" stroke={fur.stripe} strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" opacity="0.88">
        <path d="M50 30 L54 39 L58 31 L62 39 L66 30" />
        <path d="M25 53 Q32 51 36 53" />
        <path d="M24 59 Q31 58 35 60" />
        <path d="M91 53 Q84 51 80 53" />
        <path d="M92 59 Q85 58 81 60" />
      </g>
    )
  }
  if (pattern === 'tuxedo') {
    return (
      <g>
        <path d="M35 86 C36 67 45 58 58 58 C71 58 80 67 81 86 Z" fill="#fbf6ee" />
        <ellipse cx="58" cy="61" rx="15" ry="8.5" fill="#fbf6ee" />
      </g>
    )
  }
  if (pattern === 'calico') {
    return (
      <g>
        <path d="M21 28 C33 25 46 31 44 45 C42 54 27 54 20 45 Z" fill="#ee8434" />
        <path d="M74 26 C87 26 96 36 93 50 C88 55 75 51 73 41 Z" fill="#3a2d28" />
        <ellipse cx="83" cy="76" rx="12" ry="9" fill="#ee8434" />
      </g>
    )
  }
  if (pattern === 'siamese') {
    return (
      <g opacity="0.82">
        <path d="M24 22 L40 31 L27 42 Z" fill="#3c2f29" />
        <path d="M92 22 L76 31 L89 42 Z" fill="#3c2f29" />
        <ellipse cx="58" cy="54" rx="22" ry="15" fill="#46362f" opacity="0.55" />
      </g>
    )
  }
  if (pattern === 'cow') {
    return (
      <g fill="#26201d">
        <ellipse cx="36" cy="40" rx="11" ry="8" transform="rotate(-18 36 40)" />
        <ellipse cx="80" cy="44" rx="9" ry="12" transform="rotate(14 80 44)" />
        <ellipse cx="44" cy="76" rx="10" ry="7" />
        <circle cx="76" cy="74" r="7" />
      </g>
    )
  }
  if (pattern === 'bandaid') {
    return (
      <g>
        {/* Black-and-purple bruised eye ring */}
        <ellipse cx="73" cy="49" rx="13" ry="11" fill="#6d438a" opacity="0.52" />
        {/* Criss-cross comic bandaid on cheek */}
        <g transform="translate(27 57) rotate(-24)">
          <rect x="0" y="0" width="19" height="8" rx="3" fill="#f3c79b" stroke={INK} strokeWidth="2.1" />
          <rect x="6" y="0.5" width="7" height="7" fill="#fae2c8" stroke={INK} strokeWidth="1.2" />
          <circle cx="3.2" cy="4" r="0.9" fill={INK} />
          <circle cx="15.8" cy="4" r="0.9" fill={INK} />
        </g>
      </g>
    )
  }
  return null
}

/* Stray curly Oatmeal hairs & panic sweat drops rendered ABOVE outline */
function CatSurfaceQuirks({ furId, pattern }) {
  return (
    <>
      {(furId === 'potato' || pattern === 'hairy') && (
        <g fill="none" stroke={INK} strokeWidth="2" strokeLinecap="round">
          <path d="M46 27 Q43 18 48 16" />
          <path d="M68 27 Q73 19 69 15" />
          <path d="M22 46 Q14 41 16 36" />
          <path d="M94 48 Q102 44 100 38" />
          <path d="M21 71 Q14 70 15 65" />
          <path d="M94 72 Q102 74 100 68" />
          <path d="M56 32 Q59 27 55 24" />
        </g>
      )}
      {pattern === 'sweat' && (
        <g>
          <path
            d="M27 33 C23 39 22 43 26 45 C30 46 32 42 29 37 Z"
            fill="#66d9ff"
            stroke={INK}
            strokeWidth="2.2"
            strokeLinejoin="round"
          />
          <path
            d="M89 35 C86 41 85 45 89 47 C93 48 95 44 92 39 Z"
            fill="#66d9ff"
            stroke={INK}
            strokeWidth="2.2"
            strokeLinejoin="round"
          />
          <path
            d="M82 26 C80 30 80 33 83 34 C85 35 87 32 85 29 Z"
            fill="#9ae8ff"
            stroke={INK}
            strokeWidth="1.8"
          />
        </g>
      )}
    </>
  )
}

function CatEyes({ eyes, dead, blind }) {
  if (dead) {
    return (
      <g stroke={INK} strokeWidth="3.5" strokeLinecap="round">
        <path d="M39 43 L49 53 M49 43 L39 53" />
        <path d="M67 43 L77 53 M77 43 L67 53" />
      </g>
    )
  }
  if (blind) {
    return (
      <g>
        <path
          d="M25 43 Q58 38 91 43 L89 56 Q58 52 27 56 Z"
          fill="#2d2420"
          stroke={INK}
          strokeWidth="3"
          strokeLinejoin="round"
        />
        <path d="M89 47 L102 42 M89 52 L101 56" stroke="#2d2420" strokeWidth="4.2" strokeLinecap="round" />
        <path d="M89 47 L102 42 M89 52 L101 56" stroke={INK} strokeWidth="1.6" strokeLinecap="round" />
      </g>
    )
  }
  if (eyes === 'lasers') {
    return (
      <g>
        {/* Twin glowing cartoon laser beams shooting out of eyes */}
        <path d="M42 48 L-8 38 L-8 49 Z" fill="#ff3b30" opacity="0.88" />
        <path d="M42 48 L-8 42 L-8 46 Z" fill="#fff2a6" />
        <path d="M74 48 L124 38 L124 49 Z" fill="#ff3b30" opacity="0.88" />
        <path d="M74 48 L124 42 L124 46 Z" fill="#fff2a6" />
        <circle cx="43" cy="48" r="8" fill="#ff453a" stroke={INK} strokeWidth="3" />
        <circle cx="73" cy="48" r="8" fill="#ff453a" stroke={INK} strokeWidth="3" />
        <circle cx="43" cy="48" r="3.4" fill="#fff6bd" />
        <circle cx="73" cy="48" r="3.4" fill="#fff6bd" />
      </g>
    )
  }
  if (eyes === 'spiral') {
    return (
      <g>
        <circle cx="43" cy="48" r="9" fill="#fffdf8" stroke={INK} strokeWidth="3" />
        <circle cx="73" cy="48" r="9" fill="#fffdf8" stroke={INK} strokeWidth="3" />
        <path
          d="M43 48 C43 46 46 46 46 48 C46 51 40 52 39 48 C38 44 45 42 48 46"
          fill="none"
          stroke={INK}
          strokeWidth="2.2"
          strokeLinecap="round"
        />
        <path
          d="M73 48 C73 46 76 46 76 48 C76 51 70 52 69 48 C68 44 75 42 78 46"
          fill="none"
          stroke={INK}
          strokeWidth="2.2"
          strokeLinecap="round"
        />
      </g>
    )
  }
  if (eyes === 'wide') {
    return (
      <g>
        {/* Huge bloodshot manic panic eyes */}
        <circle cx="42" cy="47" r="10.4" fill="#fffdf8" stroke={INK} strokeWidth="3" />
        <circle cx="74" cy="47" r="10.4" fill="#fffdf8" stroke={INK} strokeWidth="3" />
        <path d="M33 44 L37 46 M34 52 L38 50 M83 43 L79 45 M82 52 L78 50" stroke="#e5484d" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="42" cy="47" r="2.3" fill={INK} />
        <circle cx="74" cy="47" r="2.3" fill={INK} />
      </g>
    )
  }
  if (eyes === 'angry') {
    return (
      <g>
        {/* Red rage-vein mark on forehead */}
        <path d="M54 32 L57 35 L54 38 M62 32 L59 35 L62 38" fill="none" stroke="#e5484d" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        <ellipse cx="43" cy="50" rx="8" ry="6.8" fill="#ffe8e8" stroke={INK} strokeWidth="2.8" />
        <ellipse cx="73" cy="50" rx="8" ry="6.8" fill="#ffe8e8" stroke={INK} strokeWidth="2.8" />
        <circle cx="46" cy="50" r="2.5" fill={INK} />
        <circle cx="70" cy="50" r="2.5" fill={INK} />
        <path d="M33 40 L53 47" stroke={INK} strokeWidth="4" strokeLinecap="round" />
        <path d="M83 40 L63 47" stroke={INK} strokeWidth="4" strokeLinecap="round" />
      </g>
    )
  }
  if (eyes === 'chill') {
    return (
      <g>
        {/* Heavy 3am Monday eye bags + dead-inside eyes */}
        <path d="M36 57 Q43 61 51 56" fill="none" stroke="#6c5163" strokeWidth="2.2" strokeLinecap="round" opacity="0.78" />
        <path d="M65 56 Q73 61 80 57" fill="none" stroke="#6c5163" strokeWidth="2.2" strokeLinecap="round" opacity="0.78" />
        <ellipse cx="43" cy="50" rx="8" ry="5.5" fill="#fffdf8" stroke={INK} strokeWidth="2.8" />
        <ellipse cx="73" cy="50" rx="8" ry="5.5" fill="#fffdf8" stroke={INK} strokeWidth="2.8" />
        <circle cx="43" cy="52" r="2.4" fill={INK} />
        <circle cx="73" cy="52" r="2.4" fill={INK} />
        <path d="M33 47 L53 48.5" stroke={INK} strokeWidth="3.8" strokeLinecap="round" />
        <path d="M63 48.5 L83 47" stroke={INK} strokeWidth="3.8" strokeLinecap="round" />
      </g>
    )
  }
  if (eyes === 'happy') {
    return (
      <g>
        {/* Fake strained passive-aggressive smile squint + twitch */}
        <path d="M35 51 Q43 41 51 51" fill="none" stroke={INK} strokeWidth="3.6" strokeLinecap="round" />
        <path d="M65 51 Q73 41 81 51" fill="none" stroke={INK} strokeWidth="3.6" strokeLinecap="round" />
        <path d="M33 54 L38 53 M83 54 L78 53" stroke={INK} strokeWidth="2" strokeLinecap="round" />
        <path d="M81 36 L85 33 M82 39 L87 38" stroke="#e5484d" strokeWidth="2" strokeLinecap="round" />
      </g>
    )
  }
  if (eyes === 'star') {
    return (
      <g>
        {/* Greedy $$$ money eyes */}
        <circle cx="43" cy="48" r="8.8" fill="#e6ffe8" stroke={INK} strokeWidth="2.8" />
        <circle cx="73" cy="48" r="8.8" fill="#e6ffe8" stroke={INK} strokeWidth="2.8" />
        <text x="43" y="52.5" textAnchor="middle" fontSize="13.5" fontWeight="900" fill="#1b8a42" stroke={INK} strokeWidth="0.6">$</text>
        <text x="73" y="52.5" textAnchor="middle" fontSize="13.5" fontWeight="900" fill="#1b8a42" stroke={INK} strokeWidth="0.6">$</text>
      </g>
    )
  }
  // Classic Oatmeal EXTREME asymmetrical lopsided derp eyes
  return (
    <g>
      <circle cx="42" cy="47.5" r="10" fill="#fffdf8" stroke={INK} strokeWidth="3.1" />
      <circle cx="74" cy="49" r="6.8" fill="#fffdf8" stroke={INK} strokeWidth="3" />
      <path d="M33 46 L36 47" stroke="#e5484d" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="38.2" cy="45" r="2.7" fill={INK} />
      <circle cx="77.2" cy="51.2" r="2.4" fill={INK} />
    </g>
  )
}

function CatMouth({ mouth, dead }) {
  const nose = (
    <path
      d="M54.5 55 L61.5 55 L58 59 Z"
      fill="#f48b94"
      stroke={INK}
      strokeWidth="2.2"
      strokeLinejoin="round"
    />
  )

  if (dead) {
    return (
      <g>
        {nose}
        <path d="M49 65 Q58 60 67 65" fill="none" stroke={INK} strokeWidth="2.8" strokeLinecap="round" />
        <path d="M59 64 C61 75 68 75 66 64" fill="#ff748c" stroke={INK} strokeWidth="2.2" />
      </g>
    )
  }

  if (mouth === 'rainbow') {
    return (
      <g>
        {nose}
        {/* Rainbow-Ralphing Cat iconic waterfall puke */}
        <path d="M47 63 C48 59 68 59 69 63 L73 96 L43 96 Z" fill="#ff4b4b" />
        <path d="M50 63 L66 63 L69 96 L47 96 Z" fill="#ff9e2c" />
        <path d="M52.5 63 L63.5 63 L65.5 96 L50.5 96 Z" fill="#ffe44d" />
        <path d="M55 63 L61 63 L62.5 96 L53.5 96 Z" fill="#46d468" />
        <path d="M57 63 L59.5 63 L60 96 L56.5 96 Z" fill="#4da6ff" />
        <path d="M47 63 L43 96 M69 63 L73 96" stroke={INK} strokeWidth="2.8" strokeLinecap="round" />
        {/* Open barfing mouth rim */}
        <path
          d="M46 64 C47 58 69 58 70 64 C66 67 50 67 46 64 Z"
          fill="#7a1c28"
          stroke={INK}
          strokeWidth="2.8"
          strokeLinejoin="round"
        />
      </g>
    )
  }

  if (mouth === 'drool') {
    return (
      <g>
        {nose}
        <path
          d="M46 62 Q58 72 70 62 Q66 74 58 74 Q50 74 46 62 Z"
          fill="#8c2330"
          stroke={INK}
          strokeWidth="2.6"
          strokeLinejoin="round"
        />
        <rect x="52" y="63" width="5" height="4" rx="1" fill="#ffffff" stroke={INK} strokeWidth="1.5" />
        {/* Giant glossy slobber puddle dripping down */}
        <path
          d="M61 67 C63 75 68 85 64 90 C61 93 57 90 58 84 C58.5 78 58 72 58 68 Z"
          fill="#74dcff"
          stroke={INK}
          strokeWidth="2.2"
          strokeLinejoin="round"
        />
        <circle cx="62" cy="84" r="1.6" fill="#ffffff" />
      </g>
    )
  }

  if (mouth === 'beard') {
    return (
      <g>
        <path
          d="M36 58 C32 71 38 84 47 88 C52 90 55 85 58 89 C61 85 65 90 70 88 C79 84 84 71 80 58 C72 62 64 60 58 60 C52 60 44 62 36 58 Z"
          fill="#5c4030"
          stroke={INK}
          strokeWidth="3.1"
          strokeLinejoin="round"
        />
        <path d="M45 69 L47 79 M58 68 L58 81 M71 69 L69 79" stroke="#362218" strokeWidth="2.2" strokeLinecap="round" />
        {/* Random tiny bone stuck inside the shaggy beard */}
        <g transform="translate(65 73) rotate(22)">
          <line x1="0" y1="3" x2="11" y2="3" stroke="#faf3e3" strokeWidth="3.4" strokeLinecap="round" />
          <circle cx="0" cy="1.8" r="2" fill="#faf3e3" stroke={INK} strokeWidth="1.3" />
          <circle cx="0" cy="4.4" r="2" fill="#faf3e3" stroke={INK} strokeWidth="1.3" />
          <circle cx="11" cy="1.8" r="2" fill="#faf3e3" stroke={INK} strokeWidth="1.3" />
          <circle cx="11" cy="4.4" r="2" fill="#faf3e3" stroke={INK} strokeWidth="1.3" />
        </g>
        {nose}
        <path d="M53 63 Q58 66 63 63" fill="none" stroke="#f6e4c4" strokeWidth="2.3" strokeLinecap="round" />
      </g>
    )
  }

  if (mouth === 'blep') {
    return (
      <g>
        {/* Ridiculously long wiggly sloppy tongue hanging way out */}
        <path
          d="M55 62 C55 74 63 82 69 78 C73 75 70 67 63 63 Z"
          fill="#ff6e88"
          stroke={INK}
          strokeWidth="2.5"
          strokeLinejoin="round"
        />
        <path d="M59 66 Q63 72 66 74" fill="none" stroke="#c93b56" strokeWidth="1.8" strokeLinecap="round" />
        {nose}
        <path d="M49 62 Q54 66 58 61 Q62 66 67 62" fill="none" stroke={INK} strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    )
  }

  if (mouth === 'fangs') {
    return (
      <g>
        {nose}
        {/* Crooked hillbilly snaggletooth grin */}
        <path d="M46 62 Q58 68 70 61" fill="none" stroke={INK} strokeWidth="3" strokeLinecap="round" />
        <path d="M49 63 L51 72 L55 64 Z" fill="#fffdf2" stroke={INK} strokeWidth="2" strokeLinejoin="round" />
        <rect x="57" y="64" width="4.5" height="4.8" rx="0.8" fill="#fffdf2" stroke={INK} strokeWidth="1.8" />
        <path d="M67 62 L65 70 L62 64 Z" fill="#fffdf2" stroke={INK} strokeWidth="2" strokeLinejoin="round" />
      </g>
    )
  }

  if (mouth === 'scream') {
    return (
      <g>
        {nose}
        {/* Unhinged giant screaming mouth with dangling uvula */}
        <path
          d="M44 65 C45 58 71 58 72 65 C73 77 65 81 58 81 C51 81 43 77 44 65 Z"
          fill="#7a1824"
          stroke={INK}
          strokeWidth="3"
          strokeLinejoin="round"
        />
        <path d="M49 62 L51 66 L54 62 L58 66 L62 62 L65 66 L67 62" fill="#ffffff" stroke={INK} strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M56 64 C56 70 60 70 60 64" fill="#ff7c8e" stroke={INK} strokeWidth="1.6" />
        <path d="M49 77 Q58 71 67 77" fill="#ff667e" stroke={INK} strokeWidth="1.8" />
      </g>
    )
  }

  if (mouth === 'smug') {
    return (
      <g>
        {nose}
        <path d="M48 64 Q60 68 71 59" fill="none" stroke={INK} strokeWidth="3" strokeLinecap="round" />
        <path d="M68 57 L73 61" stroke={INK} strokeWidth="2" strokeLinecap="round" />
      </g>
    )
  }

  // Unhinged deadpan :3
  return (
    <g>
      {nose}
      <path d="M49 63 Q54 67 58 61 Q62 67 67 63" fill="none" stroke={INK} strokeWidth="2.9" strokeLinecap="round" strokeLinejoin="round" />
    </g>
  )
}

function CatHatFront({ hat, isTower }) {
  const effectiveHat = hat !== 'none' ? hat : (isTower ? 'crown' : 'none')
  if (effectiveHat === 'none' || effectiveHat === 'toast') return null

  if (effectiveHat === 'cone') {
    // Front bottom rim of Cone of Shame curving under the chin
    return (
      <path
        d="M24 81 Q58 92 92 81"
        fill="none"
        stroke={INK}
        strokeWidth="3.2"
        strokeLinecap="round"
      />
    )
  }

  if (effectiveHat === 'underwear') {
    return (
      <g>
        {/* Classic Oatmeal superhero white tighty-whities stretched over the head */}
        <path
          d="M25 27 C28 11 88 11 91 27 L86 34 C76 30 68 35 64 38 L52 38 C48 35 40 30 30 34 Z"
          fill="#fbfaf6"
          stroke={INK}
          strokeWidth="3.1"
          strokeLinejoin="round"
        />
        {/* Striped elastic waistband across forehead */}
        <path
          d="M26 24 Q58 19 90 24 L89 29 Q58 24 27 29 Z"
          fill="#e2e8f0"
          stroke={INK}
          strokeWidth="2.3"
        />
        <path d="M29 26 Q58 21.5 87 26" fill="none" stroke="#e5484d" strokeWidth="1.8" />
        {/* Classic Y-fly seam */}
        <path d="M51 28 Q58 34 58 38 M65 28 Q58 34 58 38" fill="none" stroke="#9aa3b2" strokeWidth="1.8" strokeLinecap="round" />
      </g>
    )
  }

  if (effectiveHat === 'poop') {
    return (
      <g>
        {/* Stink squiggles */}
        <path d="M38 11 Q35 6 39 2 M79 11 Q82 6 78 2" fill="none" stroke="#8ad95b" strokeWidth="2.2" strokeLinecap="round" />
        {/* 3-tier cartoon brown swirl */}
        <path
          d="M36 29 C34 22 44 20 58 20 C72 20 82 22 80 29 C76 32 40 32 36 29 Z"
          fill="#7a4824"
          stroke={INK}
          strokeWidth="3"
          strokeLinejoin="round"
        />
        <path
          d="M42 22 C41 15 49 13 58 13 C67 13 75 15 74 22 Z"
          fill="#8c542b"
          stroke={INK}
          strokeWidth="2.9"
          strokeLinejoin="round"
        />
        <path
          d="M49 14 C50 8 56 3 61 4 C59 8 66 9 67 14 Z"
          fill="#9e6033"
          stroke={INK}
          strokeWidth="2.8"
          strokeLinejoin="round"
        />
        <circle cx="51" cy="24" r="1.5" fill="rgba(255,255,255,0.28)" />
      </g>
    )
  }

  if (effectiveHat === 'tin') {
    return (
      <g>
        {/* Crinkled conspiracy-theory tinfoil hat with bent antenna */}
        <path
          d="M27 30 L42 15 L58 -3 L72 14 L89 30 L74 27 L58 31 L42 27 Z"
          fill="#cfd6de"
          stroke={INK}
          strokeWidth="3.1"
          strokeLinejoin="round"
        />
        <path d="M58 -3 L66 -8" stroke={INK} strokeWidth="2.6" strokeLinecap="round" />
        <circle cx="67" cy="-8.5" r="2.6" fill="#e5edf5" stroke={INK} strokeWidth="2" />
        <path d="M44 26 L58 4 L69 26 M40 19 L55 15 L71 20" fill="none" stroke="#8591a0" strokeWidth="2" strokeLinejoin="round" />
      </g>
    )
  }

  if (effectiveHat === 'taco') {
    return (
      <g>
        <path d="M33 28 Q45 11 58 15 Q71 10 83 28 Z" fill="#52b848" stroke={INK} strokeWidth="2.6" strokeLinejoin="round" />
        <circle cx="47" cy="20" r="3.6" fill="#e5484d" stroke={INK} strokeWidth="1.8" />
        <circle cx="67" cy="19" r="3.6" fill="#e5484d" stroke={INK} strokeWidth="1.8" />
        <path d="M29 29 C32 9 84 9 87 29 Z" fill="#f5c654" stroke={INK} strokeWidth="3.2" strokeLinejoin="round" />
        <circle cx="44" cy="22" r="1.5" fill="#c78b26" />
        <circle cx="58" cy="17" r="1.5" fill="#c78b26" />
        <circle cx="72" cy="23" r="1.5" fill="#c78b26" />
      </g>
    )
  }

  if (effectiveHat === 'melon') {
    return (
      <g>
        <path d="M29 30 C32 8 84 8 87 30 Z" fill="#43a854" stroke={INK} strokeWidth="3.2" strokeLinejoin="round" />
        <path d="M43 15 Q41 22 42 29 M58 13 L58 29 M73 15 Q75 22 74 29" stroke="#226630" strokeWidth="3.2" strokeLinecap="round" />
        <path d="M31 29 Q58 25 85 29" fill="none" stroke="#d8f5c4" strokeWidth="2.4" />
      </g>
    )
  }

  if (effectiveHat === 'crown') {
    return (
      <g transform="rotate(-9 58 22)">
        <path
          d="M38 29 L35 11 L49 19 L58 6 L67 19 L81 11 L78 29 Z"
          fill="#f8c846"
          stroke={INK}
          strokeWidth="3"
          strokeLinejoin="round"
        />
        <circle cx="58" cy="21.5" r="2.6" fill="#e5484d" stroke={INK} strokeWidth="1.4" />
        <circle cx="46" cy="23.5" r="2" fill="#52b8ff" stroke={INK} strokeWidth="1.3" />
        <circle cx="70" cy="23.5" r="2" fill="#52b8ff" stroke={INK} strokeWidth="1.3" />
      </g>
    )
  }

  if (effectiveHat === 'wizard') {
    return (
      <g>
        <path d="M25 30 Q58 24 91 30 Q58 34 25 30 Z" fill="#6b4bb8" stroke={INK} strokeWidth="3" strokeLinejoin="round" />
        <path d="M39 28 L55 1 L79 28 Z" fill="#7c59d1" stroke={INK} strokeWidth="3.2" strokeLinejoin="round" />
        <circle cx="56" cy="16" r="2.4" fill="#ffd966" />
        <circle cx="65" cy="22" r="1.8" fill="#ffd966" />
        <circle cx="49" cy="23" r="1.6" fill="#ffd966" />
      </g>
    )
  }

  if (effectiveHat === 'bomb') {
    return (
      <g>
        <circle cx="58" cy="19" r="12" fill="#2c2725" stroke={INK} strokeWidth="3.1" />
        <rect x="54" y="5" width="8" height="4.8" rx="1.5" fill="#524a46" stroke={INK} strokeWidth="2.2" />
        <path d="M58 5 Q64 -2 72 2" fill="none" stroke="#d8b994" strokeWidth="2.6" strokeLinecap="round" />
        <path
          d="M73 -3 L75.5 1.2 L80 0.5 L76.8 4 L79 7.8 L74.5 6 L71 8.5 L72 4.2 L68.5 1.8 L72.5 1.4 Z"
          fill="#ff5722"
          stroke="#ffe04d"
          strokeWidth="1.2"
        />
        <circle cx="53.5" cy="16" r="2.6" fill="rgba(255,255,255,0.3)" />
      </g>
    )
  }

  if (effectiveHat === 'party') {
    return (
      <g>
        <path d="M40 29 L58 2 L76 29 Z" fill="#ff5e7e" stroke={INK} strokeWidth="3" strokeLinejoin="round" />
        <circle cx="55" cy="19" r="2.5" fill="#ffe066" />
        <circle cx="64" cy="24" r="2.2" fill="#6be5ff" />
        <circle cx="58" cy="2.5" r="4" fill="#ffe066" stroke={INK} strokeWidth="2.2" />
      </g>
    )
  }

  if (effectiveHat === 'beanie') {
    return (
      <g>
        <path d="M32 30 C34 11 82 11 84 30 Z" fill="#f25c3b" stroke={INK} strokeWidth="3.2" strokeLinejoin="round" />
        <rect x="30" y="25" width="56" height="7" rx="3.5" fill="#d94626" stroke={INK} strokeWidth="2.8" />
        <circle cx="58" cy="11" r="4.5" fill="#f25c3b" stroke={INK} strokeWidth="2.6" />
      </g>
    )
  }

  return null
}

function CatAccessory({ acc, fur }) {
  if (acc === 'knife') {
    return (
      <g>
        {/* Cartoon shiny kitchen knife held menacingly by cat's paw! */}
        <path
          d="M101 58 L103 20 C114 23 118 42 112 58 Z"
          fill="#e2e8f0"
          stroke={INK}
          strokeWidth="3"
          strokeLinejoin="round"
        />
        <path d="M106 27 L105 53" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
        <rect x="99" y="57" width="13" height="5" rx="1.5" fill="#7c5638" stroke={INK} strokeWidth="2.2" />
        <rect x="101.5" y="61" width="8" height="17" rx="3" fill="#473225" stroke={INK} strokeWidth="2.5" />
        {/* Stubby paw gripping knife handle */}
        <ellipse cx="104" cy="69" rx="7.5" ry="6" fill={fur.fill} stroke={INK} strokeWidth="3" />
      </g>
    )
  }
  if (acc === 'stink') {
    return (
      <g>
        {/* Cartoon green stink fumes + buzzing flies */}
        <path d="M6 34 Q1 25 7 18 Q12 11 7 4" fill="none" stroke="#8ad95b" strokeWidth="2.8" strokeLinecap="round" />
        <path d="M109 36 Q115 27 109 19 Q104 12 110 5" fill="none" stroke="#8ad95b" strokeWidth="2.8" strokeLinecap="round" />
        {/* Fly 1 */}
        <ellipse cx="13" cy="13" rx="3.4" ry="2.2" fill="#231f1e" />
        <ellipse cx="12" cy="10" rx="2.4" ry="1.4" fill="#eaf6ff" stroke={INK} strokeWidth="0.9" />
        {/* Fly 2 */}
        <ellipse cx="104" cy="15" rx="3.2" ry="2.1" fill="#231f1e" />
        <ellipse cx="105" cy="12" rx="2.4" ry="1.4" fill="#eaf6ff" stroke={INK} strokeWidth="0.9" />
        {/* Fly 3 */}
        <ellipse cx="111" cy="54" rx="2.8" ry="1.9" fill="#231f1e" />
        <ellipse cx="112" cy="51.5" rx="2.1" ry="1.2" fill="#eaf6ff" stroke={INK} strokeWidth="0.8" />
      </g>
    )
  }
  if (acc === 'fish') {
    return (
      <g transform="translate(66 64) rotate(16)">
        {/* Half-eaten fish skeleton dangling from mouth */}
        <line x1="0" y1="6" x2="26" y2="6" stroke="#f6f1e7" strokeWidth="3" strokeLinecap="round" />
        <line x1="0" y1="6" x2="26" y2="6" stroke={INK} strokeWidth="1.3" />
        <path d="M8 1 L8 11 M14 1.5 L14 10.5 M20 2.5 L20 9.5" stroke="#f6f1e7" strokeWidth="2.8" strokeLinecap="round" />
        <path d="M8 1 L8 11 M14 1.5 L14 10.5 M20 2.5 L20 9.5" stroke={INK} strokeWidth="1.2" strokeLinecap="round" />
        <path d="M25 6 L33 1 L31 6 L33 11 Z" fill="#f6f1e7" stroke={INK} strokeWidth="2" strokeLinejoin="round" />
      </g>
    )
  }
  if (acc === 'shades') {
    return (
      <g>
        {/* Pixelated Deal-With-It Thug Life shades */}
        <path
          d="M27 42 H89 V47 H85 V52 H80 V55 H66 V52 H62 V47 H54 V52 H50 V55 H36 V52 H31 V47 H27 Z"
          fill="#12100f"
          stroke={INK}
          strokeWidth="2"
          strokeLinejoin="round"
        />
        <rect x="34" y="45" width="4" height="3" fill="#ffffff" />
        <rect x="38" y="48" width="4" height="3" fill="#ffffff" />
        <rect x="65" y="45" width="4" height="3" fill="#ffffff" />
        <rect x="69" y="48" width="4" height="3" fill="#ffffff" />
      </g>
    )
  }
  if (acc === 'bowtie') {
    return (
      <g>
        <path d="M58 76 L45 70 L45 82 Z" fill="#e5484d" stroke={INK} strokeWidth="2.4" strokeLinejoin="round" />
        <path d="M58 76 L71 70 L71 82 Z" fill="#e5484d" stroke={INK} strokeWidth="2.4" strokeLinejoin="round" />
        <circle cx="58" cy="76" r="3.4" fill="#ff7452" stroke={INK} strokeWidth="2.2" />
      </g>
    )
  }
  if (acc === 'scarf') {
    return (
      <g>
        <path d="M31 73 Q58 79 85 73 L87 82 Q58 87 29 82 Z" fill="#e5484d" stroke={INK} strokeWidth="2.8" strokeLinejoin="round" />
        <path d="M44 76 L43 83 M58 77 L58 85 M72 76 L73 83" stroke="#ffd466" strokeWidth="3" />
      </g>
    )
  }
  if (acc === 'monocle') {
    return (
      <g>
        <circle cx="74" cy="49" r="10.4" fill="rgba(166, 224, 255, 0.24)" stroke="#f0be4f" strokeWidth="3" />
        <path d="M84 53 Q88 66 82 77" fill="none" stroke="#f0be4f" strokeWidth="2.2" strokeLinecap="round" />
      </g>
    )
  }
  if (acc === 'collar') {
    return (
      <g>
        <path d="M34 74 Q58 80 82 74" fill="none" stroke="#e5484d" strokeWidth="5.5" strokeLinecap="round" />
        <path d="M34 74 Q58 80 82 74" fill="none" stroke={INK} strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="58" cy="80" r="4.6" fill="#f8c846" stroke={INK} strokeWidth="2.2" />
      </g>
    )
  }
  return null
}

export default React.memo(function CatAvatar({
  avatar = null,
  name = '',
  size = 50,
  dead = false,
  blind = false,
  isTower = false,
  className = '',
}) {
  const uid = useId().replace(/:/g, '')
  const cfg = normalizeAvatar(avatar, name)
  const fur = FUR_MAP[cfg.fur] || FUR_MAP.ginger
  const clipId = `cat-body-${uid}`

  const width = Math.round(size * 1.24)
  const height = size

  // Lumpy asymmetrical Oatmeal potato-cat silhouette!
  const bodyPath = cfg.fur === 'potato'
    ? 'M22 87 C18 67 20 49 27 37 C28 24 37 22 45 27 C54 24 65 24 73 27 C81 21 89 24 90 38 C96 50 98 67 93 87 Z'
    : 'M22 87 C19 69 20 53 26 42 L21 19 C21 15 25 14 28 17 L44 29 C52 26 64 26 72 29 L88 16 C92 14 95 16 95 20 L90 42 C96 53 97 69 94 87 Z'

  return (
    <svg
      className={`cat-avatar-svg ${dead ? 'is-dead' : ''} ${className}`.trim()}
      width={width}
      height={height}
      viewBox="-10 -12 136 110"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <clipPath id={clipId}>
          <path d={bodyPath} />
        </clipPath>
      </defs>

      {/* Back layer for wrap-around hats (Toast / Cone of Shame) */}
      <CatHatBack hat={cfg.hat} />

      {/* Ghost halo when dead */}
      {dead && (
        <ellipse
          cx="58"
          cy="8"
          rx="17"
          ry="4.4"
          fill="none"
          stroke="#f8d86c"
          strokeWidth="2.8"
        />
      )}

      {/* Squishy Oatmeal Cat Body */}
      <g clipPath={`url(#${clipId})`}>
        <rect x="14" y="10" width="88" height="80" fill={fur.fill} />
        <path d="M16 73 Q58 83 100 73 L100 94 L16 94 Z" fill={fur.shade} opacity="0.34" />
        <CatFurDetails furId={cfg.fur} fur={fur} />
        <CatPattern pattern={cfg.pattern} fur={fur} />
      </g>

      {/* Inner pink ears (hidden for lumpy potato cat) */}
      {cfg.fur !== 'potato' && (
        <>
          <path d="M26 23 L37 31 L29 36 Z" fill={fur.ear} />
          <path d="M90 23 L79 31 L87 36 Z" fill={fur.ear} />
        </>
      )}

      {/* Thick wobbly comic ink outline */}
      <path
        d={bodyPath}
        fill="none"
        stroke={INK}
        strokeWidth="3.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Stray hairs & panic sweat drops */}
      <CatSurfaceQuirks furId={cfg.fur} pattern={cfg.pattern} />

      {/* Crooked chaotic whiskers */}
      <g stroke={INK} strokeWidth="2.3" strokeLinecap="round">
        <path d="M9 50 L25 53" />
        <path d="M6 58 L24 58" />
        <path d="M10 66 L25 63" />
        <path d="M107 49 L91 53" />
        <path d="M110 58 L92 58" />
        <path d="M106 66 L91 63" />
      </g>

      {/* Stubby little paws gripping the nameplate (drawn below rainbow puke so puke splashes over!) */}
      <g>
        <path
          d="M25 90 C24 81 30 78 35 78 C40 78 44 82 43 90 Z"
          fill={cfg.pattern === 'tuxedo' ? '#fbf6ee' : fur.fill}
          stroke={INK}
          strokeWidth="3.2"
          strokeLinejoin="round"
        />
        <path d="M31 82 L31 89 M37 82 L37 89" stroke={INK} strokeWidth="1.9" strokeLinecap="round" />
        <path
          d="M73 90 C72 82 76 78 81 78 C86 78 92 81 91 90 Z"
          fill={cfg.pattern === 'tuxedo' ? '#fbf6ee' : fur.fill}
          stroke={INK}
          strokeWidth="3.2"
          strokeLinejoin="round"
        />
        <path d="M79 82 L79 89 M85 82 L85 89" stroke={INK} strokeWidth="1.9" strokeLinecap="round" />
      </g>

      {/* Expressive unhinged face */}
      <CatEyes eyes={cfg.eyes} dead={dead} blind={blind} />
      <CatMouth mouth={cfg.mouth} dead={dead} />

      {/* Hat front & hilarious accessories */}
      <CatHatFront hat={cfg.hat} isTower={isTower && !dead} />
      <CatAccessory acc={cfg.acc} fur={fur} />
    </svg>
  )
})
