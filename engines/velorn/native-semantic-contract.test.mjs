// Real pinned source semantics, not scripted proof of neural creativity.
import test from 'node:test'
import assert from 'node:assert/strict'
import { buildTextAnimationPresetKeyframes } from '../../third_party/velorn/src/utils/textAnimationPresets.js'
import { getValueAtTime, getAnimatedTransform } from '../../third_party/velorn/src/utils/keyframes.js'

test('Native fade uses base opacity as plateau, including intentionally invisible zero', () => {
  for (const opacity of [0, 25, 100]) {
    const { keyframes } = buildTextAnimationPresetKeyframes({
      presetId: 'fade', mode: 'inOut', clipDuration: 2, fps: 24,
      baseTransform: { opacity },
    })
    assert.deepEqual(keyframes.opacity.map(k => k.value), [0, opacity, opacity, 0])
    assert.equal(getValueAtTime(keyframes.opacity, 1, 100), opacity)
  }
})

test('Native explicit opacity keys override base opacity without changing the base', () => {
  const clip = { transform: { opacity: 0 }, keyframes: { opacity: [
    { time: 0, value: 0 }, { time: 0.5, value: 100 },
    { time: 1.5, value: 100 }, { time: 2, value: 0 },
  ] } }
  assert.equal(getAnimatedTransform(clip, 1).opacity, 100)
  assert.equal(clip.transform.opacity, 0)
  assert.equal(getAnimatedTransform(clip, 0).opacity, 0)
})
