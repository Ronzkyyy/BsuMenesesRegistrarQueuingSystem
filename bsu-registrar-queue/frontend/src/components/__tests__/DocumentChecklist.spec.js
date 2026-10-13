// Mounted with Vue's own createApp (the project has no @vue/test-utils).
import { afterEach, describe, expect, it } from 'vitest'
import { createApp, h, nextTick, ref } from 'vue'
import DocumentChecklist from '../DocumentChecklist.vue'

const DOCS = [
  { id: 1, name: 'Transcript of Records', short_name: 'TOR', fee: '150.00', processing_time: '5 days', requirements: 'Clearance form' },
  { id: 2, name: 'Certificate of Grades', short_name: 'COG', fee: null, processing_time: null, requirements: null },
  { id: 3, name: 'Good Moral', short_name: 'GM', fee: '0.00', processing_time: null, requirements: 'Valid ID' },
]

let app
let root

function mount(initial = []) {
  const selected = ref(initial)
  root = document.createElement('div')
  document.body.appendChild(root)
  app = createApp({
    render: () => h(DocumentChecklist, {
      documents: DOCS,
      modelValue: selected.value,
      'onUpdate:modelValue': (v) => { selected.value = v },
    }),
  })
  app.mount(root)
  return selected
}

const boxes = () => [...root.querySelectorAll('input[type=checkbox]')]

afterEach(() => {
  app?.unmount()
  root?.remove()
})

describe('DocumentChecklist', () => {
  it('lists every document with its fee label', () => {
    mount()
    expect(boxes()).toHaveLength(3)
    expect(root.textContent).toContain('₱150.00')
    expect(root.textContent).toContain('Free')
    expect(root.textContent).toContain('Processing time: 5 days')
  })

  it('emits ids in catalog order whatever order they are ticked in', async () => {
    const selected = mount()
    boxes()[2].click()
    await nextTick()
    boxes()[0].click()
    await nextTick()
    expect(selected.value).toEqual([1, 3])

    boxes()[2].click()
    await nextTick()
    expect(selected.value).toEqual([1])
  })

  it('shows requirements only for checked documents', async () => {
    mount([1])
    await nextTick()
    expect(root.textContent).toContain('Clearance form')
    expect(root.textContent).not.toContain('Valid ID')
  })

  it('shows the count and a partial total when a fee is not listed', async () => {
    mount([1, 2])
    await nextTick()
    expect(root.textContent).toContain('2 documents selected')
    expect(root.textContent).toContain('Total of listed fees ₱150.00')
  })
})
