// frontend/src/components/settings/pricing/ComplexitySection.tsx
'use client'
//
// The complexity configuration section of the pricing settings tab: what one
// service's complexity pricing is, and the flows that change it.
//
// THE BEHAVIOURS THAT MUST SURVIVE THE VISUAL PASS, since they are behaviours
// rather than styling:
//
//   - null versus zero never collapse, read side or write side. An empty price
//     box is null, which is unpriced and routes to quote. A typed 0 is a price
//     of zero. There is no ?? 0 in this file and there must never be one, and
//     the distinction is stated in words next to the inputs rather than left
//     for the owner to infer from an empty box.
//   - A cleared parent shows no price and no price input. Prices live only at
//     the end of a chain, so an input on a parent would invite the owner to
//     type a number the server would refuse.
//   - The catch-all Other option is never priceable (rule 9) and says why. No
//     price and no input is rendered for it in any state.
//   - Every refusal reaches the owner in the server's own words, through
//     refusalMessage. There is no generic error copy in this section.
//   - Scope is immutable. There is no re-scope control here, deliberately.
//     Changing scope is delete and recreate.
//   - Deleting is a two-call sequence. The first DELETE goes without confirm
//     purely to be refused, because that refusal carries the server's own
//     census of what would be destroyed, and that census is the warning the
//     owner reads. Nothing here counts a blast radius itself.
//   - An activated service with nothing configured is a legitimate, calm
//     state, not an error.
//   - Every engagement type string comes from the config read.

import { useState, type ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  pricingApi,
  refusalMessage,
  type ComplexityDimension,
  type DimensionRole,
  type FirmTier,
  type PricingConfig,
  type ServiceCatalogEntry,
} from '@/lib/api/pricing'
import { buildServiceComplexityView, type ChainNode, type OptionSlot, type TierSlot } from './chain'
import AddDimensionForm, { type CreateConfigInput, type ParentChoice } from './AddDimensionForm'
import PricedParentDialog from './PricedParentDialog'
import DeleteConfigDialog, { type DeleteMode } from './DeleteConfigDialog'

const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'
const chipClass =
  'text-[11px] rounded-full px-2 py-0.5 bg-surface-page dark:bg-dark-page text-[#6B7280] border border-surface-border dark:border-dark-border'
const inputClass =
  'rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] px-2.5 py-1.5 w-28 focus:outline-none focus:ring-1 focus:ring-brand'

// The null versus zero law, on the way in. An empty box is null and stays
// null. Number('') is 0, which is exactly the collapse this forbids, so the
// empty case is answered before any conversion happens.
function parseMoney(raw: string): number | null {
  const trimmed = raw.trim()
  if (trimmed === '') return null
  const n = Number(trimmed)
  return Number.isNaN(n) ? null : n
}

function formatMoney(value: number | null): string {
  if (value === null) return ''
  return String(value)
}

// The same law on the way out, for display.
function priceLabel(price: number | null): string {
  if (price === null) return 'Unpriced, routes to quote'
  if (price === 0) return '0.00, priced at zero'
  return price.toFixed(2)
}

function kindLabel(kind: ComplexityDimension['kind']): string {
  if (kind === 'numeric_range') return 'Number'
  if (kind === 'categorical') return 'Choice'
  return 'Yes or no'
}

function roleSentence(role: DimensionRole, guardThreshold: number | null): string {
  if (role === 'informational') {
    return 'Collected from the lead and shown to you, never priced.'
  }
  if (role === 'guard') {
    return guardThreshold === null
      ? 'Used as a guard, routing the lead out of automation.'
      : 'Used as a guard: past ' + guardThreshold + ', the lead routes out of automation.'
  }
  return 'Priced. The answer moves the fee.'
}

function tierRangeLabel(tier: FirmTier): string {
  return tier.rangeMax === null
    ? tier.rangeMin + ' and above'
    : tier.rangeMin + ' to ' + tier.rangeMax
}

export default function ComplexitySection({
  data,
  engagementType,
  entry,
}: {
  data: PricingConfig
  engagementType: string
  entry: ServiceCatalogEntry
}) {
  const queryClient = useQueryClient()
  const view = buildServiceComplexityView(data, engagementType, entry.id)

  const [adding, setAdding] = useState(false)
  const [working, setWorking] = useState(false)
  // A create the server refused because its parent still carries a price,
  // held with the refusal that stopped it so the owner can decide.
  const [pending, setPending] = useState<{
    input: CreateConfigInput
    parent: ParentChoice
    refusal: string
  } | null>(null)
  // A delete the owner has asked for and the server has already refused once,
  // held with the census that refusal carried.
  const [deleting, setDeleting] = useState<{
    configId: string
    mode: DeleteMode
    questionLabel: string
    parentLabel: string | null
    census: string
  } | null>(null)

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['pricing-config'] })

  const scopeLabelFor = (serviceCatalogEntryId: string | null): string => {
    if (serviceCatalogEntryId === null) return 'Every service this question applies to'
    const scopedEntry = data.serviceCatalogEntries.find((e) => e.id === serviceCatalogEntryId)
    if (!scopedEntry) return 'One service'
    const type = data.engagementTypes.find((t) => t.value === scopedEntry.engagementType)
    return type ? 'Only ' + type.label : 'One service'
  }

  // Everywhere a new question could hang, built from what is already on screen
  // so the picker can only name a real tier or option. isPriced is read from
  // the config read, not decided here.
  const parentChoices: ParentChoice[] = []
  const collectParents = (nodes: ChainNode[]) => {
    for (const node of nodes) {
      const scopeLabel = scopeLabelFor(node.config.serviceCatalogEntryId)
      for (const slot of node.tierSlots) {
        parentChoices.push({
          kind: 'tier',
          id: slot.tier.id,
          label: (node.flag ? node.flag.name : node.dimension.key) + ': ' + tierRangeLabel(slot.tier),
          scopeLabel,
          isPriced: slot.tier.price !== null,
        })
        collectParents(slot.children)
      }
      for (const slot of node.optionSlots) {
        parentChoices.push({
          kind: 'option',
          id: slot.option.id,
          label: (node.flag ? node.flag.name : node.dimension.key) + ': ' + slot.option.label,
          scopeLabel,
          isPriced: slot.priceRow !== null && slot.priceRow.price !== null,
        })
        collectParents(slot.children)
      }
    }
  }
  collectParents([...view.blanket, ...view.scoped, ...view.unattached])

  // A scoped override is born as a COPY of the blanket configuration, taken
  // once, at creation. It is not a fallback and nothing stays linked: after
  // this runs, editing either one leaves the other alone.
  //
  // Only the config being created is copied, not the tree beneath it. A deep
  // clone would have to re-parent every descendant and is a separate,
  // confirmed action rather than a side effect of adding one question.
  const copyBlanketPrices = async (input: CreateConfigInput, createdConfigId: string) => {
    if (input.serviceCatalogEntryId === null) return
    const blanket = data.configs.find(
      (c) => c.dimensionId === input.dimensionId && c.serviceCatalogEntryId === null
    )
    if (!blanket) return

    const dimension = data.dimensions.find((d) => d.id === input.dimensionId)
    if (!dimension) return

    if (dimension.kind === 'numeric_range') {
      const ladder = data.tiers
        .filter((t) => t.configId === blanket.id)
        .slice()
        .sort((a, b) => a.sortOrder - b.sortOrder)
      if (ladder.length === 0) return
      await pricingApi.saveTiers(
        createdConfigId,
        // Prices are carried across exactly as they are. A blanket band that is
        // unpriced stays unpriced in the copy, and one priced at zero stays at
        // zero.
        ladder.map((t) => ({
          rangeMin: t.rangeMin,
          rangeMax: t.rangeMax,
          price: t.price,
          sortOrder: t.sortOrder,
        }))
      )
      return
    }

    if (dimension.kind === 'categorical') {
      const options = data.vocabularyOptions.filter((o) => o.dimensionId === dimension.id)
      for (const option of options) {
        const blanketPrice = data.optionPrices.find(
          (p) => p.optionId === option.id && p.serviceCatalogEntryId === null
        )
        if (!blanketPrice) continue
        // Rule 9 is the server's, and a priced Other cannot legitimately exist
        // to be copied. Attempting one here would turn a copy into a refusal
        // the owner did not ask for.
        if (option.key === 'other') continue
        await pricingApi.setOptionPrice({
          optionId: option.id,
          serviceCatalogEntryId: input.serviceCatalogEntryId,
          price: blanketPrice.price,
        })
      }
    }
  }

  const runCreate = async (input: CreateConfigInput) => {
    const created = (await pricingApi.createConfig(input)) as { id: string }
    await copyBlanketPrices(input, String(created.id))
  }

  const submitCreate = async (input: CreateConfigInput, parent: ParentChoice | undefined) => {
    setWorking(true)
    try {
      await runCreate(input)
      invalidate()
      toast.success('Question added')
      setAdding(false)
      setPending(null)
    } catch (err) {
      const message = refusalMessage(err, 'Could not add this question.')
      // The clear-and-retry path is offered only when the parent the owner
      // picked is actually carrying a price right now. Every other refusal,
      // including the ones that also involve a parent, is the server saying
      // something else, and it says it in its own words.
      if (parent && parent.isPriced) {
        setPending({ input, parent, refusal: message })
      } else {
        toast.error(message)
      }
    } finally {
      setWorking(false)
    }
  }

  // Clearing the parent price, then retrying the create the refusal stopped.
  // The tier ladder is saved back whole with one price set to null, and an
  // option price is set to null in the child's own scope, which is the scope
  // the server checked when it refused.
  const confirmClearParent = async () => {
    if (!pending) return
    setWorking(true)
    try {
      if (pending.parent.kind === 'tier') {
        const tier = data.tiers.find((t) => t.id === pending.parent.id)
        if (!tier) throw new Error('missing tier')
        const ladder = data.tiers
          .filter((t) => t.configId === tier.configId)
          .slice()
          .sort((a, b) => a.sortOrder - b.sortOrder)
        await pricingApi.saveTiers(
          tier.configId,
          ladder.map((t) => ({
            rangeMin: t.rangeMin,
            rangeMax: t.rangeMax,
            price: t.id === tier.id ? null : t.price,
            sortOrder: t.sortOrder,
          }))
        )
      } else {
        await pricingApi.setOptionPrice({
          optionId: pending.parent.id,
          serviceCatalogEntryId: pending.input.serviceCatalogEntryId,
          price: null,
        })
      }
      await runCreate(pending.input)
      invalidate()
      toast.success('Price cleared and question added')
      setPending(null)
      setAdding(false)
    } catch (err) {
      toast.error(refusalMessage(err, 'Could not clear the price on that answer.'))
      invalidate()
      setPending(null)
    } finally {
      setWorking(false)
    }
  }

  // What a nested question hangs under, in the words on screen. The census
  // names ids and counts; this names the answer that is about to be left with
  // nothing pricing it.
  const parentLabelFor = (config: ChainNode['config']): string | null => {
    if (config.parentTierId !== null) {
      const tier = data.tiers.find((t) => t.id === config.parentTierId)
      return tier ? 'the band ' + tierRangeLabel(tier) : null
    }
    if (config.parentOptionId !== null) {
      const option = data.vocabularyOptions.find((o) => o.id === config.parentOptionId)
      return option ? 'the answer ' + option.label : null
    }
    return null
  }

  // FIRST CALL, WITHOUT CONFIRM, ON PURPOSE. The server refuses it with a 422
  // whose detail is the census of everything that would go, and that text
  // becomes the dialog body. The refusal writes nothing, which is what makes
  // asking for it safe.
  const requestDelete = async (node: ChainNode) => {
    setWorking(true)
    try {
      await pricingApi.deleteConfig(node.config.id, false)
      // The server must refuse an unconfirmed delete. Arriving here means it
      // did not, so there is nothing left to warn about and pretending
      // otherwise would be theatre.
      invalidate()
      toast.success('Question removed')
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404) {
        // Not found, and nothing more. The census belongs to the firm that owns
        // the config and the server withholds it from everyone else by design.
        // Nothing here works around that.
        toast.error(refusalMessage(err, 'That configuration no longer exists.'))
        invalidate()
        return
      }
      if (status !== 422) {
        toast.error(refusalMessage(err, 'Could not remove this question.'))
        return
      }
      setDeleting({
        configId: node.config.id,
        mode:
          node.config.parentTierId !== null || node.config.parentOptionId !== null
            ? 'matrix'
            : 'additive',
        questionLabel: node.flag ? node.flag.name : node.dimension.key,
        parentLabel: parentLabelFor(node.config),
        census: refusalMessage(err, 'Could not remove this question.'),
      })
    } finally {
      setWorking(false)
    }
  }

  // SECOND CALL, with the owner's explicit agreement.
  const confirmDelete = async () => {
    if (!deleting) return
    setWorking(true)
    try {
      await pricingApi.deleteConfig(deleting.configId, true)
      invalidate()
      toast.success('Question removed')
      setDeleting(null)
    } catch (err) {
      toast.error(refusalMessage(err, 'Could not remove this question.'))
      invalidate()
      setDeleting(null)
    } finally {
      setWorking(false)
    }
  }

  const saveTiersMutation = useMutation({
    mutationFn: (vars: {
      configId: string
      tiers: { rangeMin: number; rangeMax: number | null; price: number | null; sortOrder: number }[]
    }) => pricingApi.saveTiers(vars.configId, vars.tiers),
    onSuccess: () => {
      invalidate()
      toast.success('Saved')
    },
    onError: (err) => toast.error(refusalMessage(err, 'Could not save these bands.')),
  })

  const setOptionPriceMutation = useMutation({
    mutationFn: (vars: {
      optionId: string
      serviceCatalogEntryId: string | null
      price: number | null
    }) => pricingApi.setOptionPrice(vars),
    onSuccess: () => {
      invalidate()
      toast.success('Saved')
    },
    onError: (err) => toast.error(refusalMessage(err, 'Could not save this price.')),
  })

  const nodeProps = {
    scopeLabelFor,
    deleting,
    onRequestDelete: (node: ChainNode) => void requestDelete(node),
    onConfirmDelete: () => void confirmDelete(),
    onCancelDelete: () => setDeleting(null),
    deleteWorking: working,
    onSaveTiers: (
      configId: string,
      tiers: { rangeMin: number; rangeMax: number | null; price: number | null; sortOrder: number }[]
    ) => saveTiersMutation.mutate({ configId, tiers }),
    onSetOptionPrice: (
      optionId: string,
      serviceCatalogEntryId: string | null,
      price: number | null
    ) => setOptionPriceMutation.mutate({ optionId, serviceCatalogEntryId, price }),
    saving: saveTiersMutation.isPending || setOptionPriceMutation.isPending,
  }

  return (
    <div className="flex flex-col gap-3 pt-3 border-t border-surface-border dark:border-dark-border">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className={labelClass}>Complexity pricing</span>
          <p className="text-[12px] text-[#6B7280]">
            Complexity questions sit on top of the base fee. A lead answers them on the
            intake form and the answers move the price. Blank is not zero: a question left
            unpriced routes the lead to quote, and 0.00 is a real price.
          </p>
        </div>
        {!adding && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="text-[12px] text-brand dark:text-[#EDEEF0] underline shrink-0"
          >
            Add question
          </button>
        )}
      </div>

      {/* Activated and unconfigured is a real state, not a problem. */}
      {view.isEmpty && !adding && (
        <div className="text-[12px] text-[#6B7280] bg-surface-page dark:bg-dark-page rounded-[6px] px-2.5 py-2">
          No complexity configuration yet. Leads are not asked any complexity questions
          for this service, so nothing moves the price above the base fee.
        </div>
      )}

      {adding && (
        <AddDimensionForm
          data={data}
          engagementType={engagementType}
          entry={entry}
          parentChoices={parentChoices}
          submitting={working}
          onCancel={() => {
            setAdding(false)
            setPending(null)
          }}
          onSubmit={(input) => {
            const parent = parentChoices.find(
              (p) =>
                (p.kind === 'tier' && p.id === input.parentTierId) ||
                (p.kind === 'option' && p.id === input.parentOptionId)
            )
            void submitCreate(input, parent)
          }}
        />
      )}

      {pending && (
        <PricedParentDialog
          refusal={pending.refusal}
          parentLabel={pending.parent.label}
          working={working}
          onConfirm={() => void confirmClearParent()}
          onCancel={() => setPending(null)}
        />
      )}

      {view.blanket.length > 0 && (
        <NodeGroup
          heading="Applies to every service this question covers"
          nodes={view.blanket}
          {...nodeProps}
        />
      )}

      {view.scoped.length > 0 && (
        <NodeGroup heading="Set for this service only" nodes={view.scoped} {...nodeProps} />
      )}

      {/* Shown rather than dropped. A config whose parent is not in this view
          is still a real row the firm owns, and a fee schedule screen that
          quietly omits rows is worse than one that admits it cannot place
          them. */}
      {view.unattached.length > 0 && (
        <NodeGroup
          heading="Configured, but their parent question is not shown here"
          nodes={view.unattached}
          {...nodeProps}
        />
      )}

      {view.unknownDimensionCount > 0 && (
        <div className="text-[12px] text-[#6B7280]">
          {view.unknownDimensionCount} configured{' '}
          {view.unknownDimensionCount === 1 ? 'question is' : 'questions are'} attached to
          a dimension the catalog did not return.
        </div>
      )}
    </div>
  )
}

interface NodeProps {
  scopeLabelFor: (serviceCatalogEntryId: string | null) => string
  deleting: {
    configId: string
    mode: DeleteMode
    questionLabel: string
    parentLabel: string | null
    census: string
  } | null
  onRequestDelete: (node: ChainNode) => void
  onConfirmDelete: () => void
  onCancelDelete: () => void
  deleteWorking: boolean
  onSaveTiers: (
    configId: string,
    tiers: { rangeMin: number; rangeMax: number | null; price: number | null; sortOrder: number }[]
  ) => void
  onSetOptionPrice: (
    optionId: string,
    serviceCatalogEntryId: string | null,
    price: number | null
  ) => void
  saving: boolean
}

function NodeGroup({
  heading,
  nodes,
  ...rest
}: { heading: string; nodes: ChainNode[] } & NodeProps) {
  return (
    <div className="flex flex-col gap-2">
      <div className={labelClass}>{heading}</div>
      <div className="flex flex-col gap-2">
        {nodes.map((node) => (
          <ConfigNode key={node.config.id} node={node} depth={0} {...rest} />
        ))}
      </div>
    </div>
  )
}

function ConfigNode({
  node,
  depth,
  ...rest
}: { node: ChainNode; depth: number } & NodeProps) {
  const { config, dimension, flag, unit } = node
  const { scopeLabelFor, onSaveTiers, onSetOptionPrice, saving } = rest
  const { deleting, onRequestDelete, onConfirmDelete, onCancelDelete, deleteWorking } = rest

  return (
    <div className="rounded-[6px] border border-surface-border dark:border-dark-border p-2.5 flex flex-col gap-2">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
            {flag ? flag.name : dimension.key}
          </span>
          <span className={chipClass}>{kindLabel(dimension.kind)}</span>
          {/* Scope is stated once, at the top of a chain. Everything below a
              root shares it. There is no control to change it: scope is
              immutable, and changing it is delete and recreate. */}
          {depth === 0 && (
            <span className={chipClass}>{scopeLabelFor(config.serviceCatalogEntryId)}</span>
          )}
          {/* The first call goes out without confirm and is expected to be
              refused. The refusal is the warning. */}
          <button
            type="button"
            disabled={deleteWorking}
            onClick={() => onRequestDelete(node)}
            className="text-[12px] text-[#6B7280] underline ml-auto disabled:opacity-50"
          >
            Remove
          </button>
        </div>
        <span className="text-[12px] text-[#6B7280]">
          {unit?.questionText ?? dimension.questionText ?? dimension.key}
        </span>
        <span className="text-[12px] text-[#6B7280]">
          {roleSentence(config.role, config.guardThreshold)}
          {unit ? ' Counted in ' + unit.label + '.' : ''}
        </span>
      </div>

      {deleting !== null && deleting.configId === config.id && (
        <DeleteConfigDialog
          mode={deleting.mode}
          questionLabel={deleting.questionLabel}
          parentLabel={deleting.parentLabel}
          census={deleting.census}
          working={deleteWorking}
          onConfirm={onConfirmDelete}
          onCancel={onCancelDelete}
        />
      )}

      {dimension.kind === 'numeric_range' && (
        <TierEditor
          key={node.tierSlots
            .map((s) => s.tier.id + ':' + s.tier.rangeMin + ':' + s.tier.rangeMax + ':' + s.tier.price)
            .join('|')}
          configId={config.id}
          slots={node.tierSlots}
          onSave={onSaveTiers}
          saving={saving}
          renderChild={(child) => <ConfigNode node={child} depth={depth + 1} {...rest} />}
        />
      )}

      {dimension.kind === 'categorical' && (
        <div className="flex flex-col gap-1.5">
          {node.optionSlots.length === 0 ? (
            <span className="text-[12px] text-[#6B7280]">
              This question has no answers in the catalog.
            </span>
          ) : (
            <>
              <span className="text-[12px] text-[#6B7280]">
                Leave a price blank to leave that answer unpriced, which routes the lead to
                quote. Type 0 to price it at zero, which is a real price.
              </span>
              {node.optionSlots.map((slot) => (
                <OptionRow
                  key={
                    slot.option.id +
                    ':' +
                    (slot.priceRow === null ? 'none' : String(slot.priceRow.price))
                  }
                  slot={slot}
                  scope={config.serviceCatalogEntryId}
                  onSetOptionPrice={onSetOptionPrice}
                  saving={saving}
                  renderChild={(child) => <ConfigNode node={child} depth={depth + 1} {...rest} />}
                />
              ))}
            </>
          )}
        </div>
      )}

      {dimension.kind === 'boolean' && (
        <span className="text-[12px] text-[#6B7280]">
          A yes or no question. This kind carries no bands and no answer list, so there is
          nothing on it to attach a price to.
        </span>
      )}
    </div>
  )
}

interface TierRow {
  rangeMin: string
  rangeMax: string
  price: string
  sortOrder: number
  // A band with questions inside it does not price, so its price cell is not
  // an input at all. Carried on the row so the save keeps sending null for it.
  hasChildren: boolean
}

function TierEditor({
  configId,
  slots,
  onSave,
  saving,
  renderChild,
}: {
  configId: string
  slots: TierSlot[]
  onSave: (
    configId: string,
    tiers: { rangeMin: number; rangeMax: number | null; price: number | null; sortOrder: number }[]
  ) => void
  saving: boolean
  renderChild: (child: ChainNode) => ReactNode
}) {
  const [rows, setRows] = useState<TierRow[]>(
    slots.map((slot) => ({
      rangeMin: String(slot.tier.rangeMin),
      rangeMax: slot.tier.rangeMax === null ? '' : String(slot.tier.rangeMax),
      price: formatMoney(slot.tier.price),
      sortOrder: slot.tier.sortOrder,
      hasChildren: slot.children.length > 0,
    }))
  )

  const update = (index: number, patch: Partial<TierRow>) =>
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)))

  const addRow = () =>
    setRows((prev) => [
      ...prev,
      {
        rangeMin: '',
        rangeMax: '',
        price: '',
        sortOrder: prev.length === 0 ? 0 : Math.max(...prev.map((r) => r.sortOrder)) + 1,
        hasChildren: false,
      },
    ])

  const removeRow = (index: number) => setRows((prev) => prev.filter((_, i) => i !== index))

  const save = () =>
    onSave(
      configId,
      rows.map((row) => ({
        rangeMin: Number(row.rangeMin),
        // An empty top is the open band, not a zero-width one.
        rangeMax: row.rangeMax.trim() === '' ? null : Number(row.rangeMax),
        // A band with children never sends a price, and neither does the open
        // top: both are unpriceable by rule, so neither can carry one here.
        price: row.hasChildren || row.rangeMax.trim() === '' ? null : parseMoney(row.price),
        sortOrder: row.sortOrder,
      }))
    )

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[12px] text-[#6B7280]">
        Leave a price blank to leave that band unpriced, which routes the lead to quote.
        Type 0 to price it at zero, which is a real price. Leave the top of the last band
        empty to make it open ended, and an open ended band always routes to quote rather
        than carrying a price of its own.
      </span>

      {rows.map((row, index) => (
        <div key={index} className="flex flex-col gap-1.5">
          <div className={'flex items-center gap-2 ' + (row.hasChildren ? 'opacity-50' : '')}>
            <input
              type="number"
              value={row.rangeMin}
              onChange={(e) => update(index, { rangeMin: e.target.value })}
              placeholder="From"
              className={inputClass}
            />
            <input
              type="number"
              value={row.rangeMax}
              onChange={(e) => update(index, { rangeMax: e.target.value })}
              placeholder="To (blank for open)"
              className={inputClass}
            />
            {/* No input on anything that cannot be priced, in any state: a
                cleared parent, or the open top band. An open top is quote
                territory by rule, so a box there could only ever collect a
                number the server refuses. */}
            {row.hasChildren ? (
              <span className="text-[12px] text-[#6B7280] flex-1">
                Price cleared so the questions below can price
              </span>
            ) : row.rangeMax.trim() === '' ? (
              <span className="text-[12px] text-[#6B7280] flex-1">
                Open ended, so it always routes to quote and carries no price
              </span>
            ) : (
              <input
                type="number"
                step="0.01"
                value={row.price}
                onChange={(e) => update(index, { price: e.target.value })}
                placeholder="Blank for unpriced"
                className={inputClass}
              />
            )}
            <button
              type="button"
              onClick={() => removeRow(index)}
              className="text-[12px] text-[#6B7280] underline"
            >
              Remove
            </button>
          </div>
          {slots[index]?.children.map((child) => (
            <div key={child.config.id} className="pl-3">
              {renderChild(child)}
            </div>
          ))}
        </div>
      ))}

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={addRow}
          className="text-[12px] text-brand dark:text-[#EDEEF0] underline"
        >
          Add a band
        </button>
        <button
          type="button"
          disabled={saving}
          onClick={save}
          className="rounded-[6px] bg-brand text-white text-[13px] px-3 py-1.5 disabled:opacity-50"
        >
          Save bands
        </button>
      </div>
    </div>
  )
}

function OptionRow({
  slot,
  scope,
  onSetOptionPrice,
  saving,
  renderChild,
}: {
  slot: OptionSlot
  scope: string | null
  onSetOptionPrice: (
    optionId: string,
    serviceCatalogEntryId: string | null,
    price: number | null
  ) => void
  saving: boolean
  renderChild: (child: ChainNode) => ReactNode
}) {
  const [price, setPrice] = useState(
    slot.priceRow === null ? '' : formatMoney(slot.priceRow.price)
  )
  const isClearedParent = slot.children.length > 0

  return (
    <div className="flex flex-col gap-1.5">
      <div className={'flex items-center gap-2 ' + (isClearedParent ? 'opacity-50' : '')}>
        <span className="text-[12px] text-brand dark:text-[#EDEEF0] flex-1">
          {slot.option.label}
        </span>

        {/* Rule 9. Other is never priceable, so it gets no input and no price in
            any state, and the reason is said rather than implied. */}
        {slot.isOther ? (
          <span className="text-[12px] text-[#6B7280] flex-1">
            Never priced. Other means the system could not classify the lead, so the answer
            always routes to quote.
          </span>
        ) : isClearedParent ? (
          <span className="text-[12px] text-[#6B7280] flex-1">
            Price cleared so the questions below can price
          </span>
        ) : (
          <>
            <input
              type="number"
              step="0.01"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="Blank for unpriced"
              className={inputClass}
            />
            <button
              type="button"
              disabled={saving}
              onClick={() => onSetOptionPrice(slot.option.id, scope, parseMoney(price))}
              className="rounded-[6px] border border-surface-border dark:border-dark-border text-[12px] px-2.5 py-1 text-brand dark:text-[#EDEEF0] disabled:opacity-50"
            >
              Save
            </button>
            <span className="text-[12px] text-[#6B7280] w-40 text-right">
              {slot.priceRow === null
                ? 'No price set, routes to quote'
                : priceLabel(slot.priceRow.price)}
            </span>
          </>
        )}
      </div>

      {slot.children.map((child) => (
        <div key={child.config.id} className="pl-3">
          {renderChild(child)}
        </div>
      ))}
    </div>
  )
}
