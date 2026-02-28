<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let visible = true;
  export let label = 'Drop images here';
  export let id = 'dropZone';
  export let inputId = 'fileInput';
  export let thumbsId = 'thumbs';
  export let thumbnails: string[] = [];
  export let accept = '.png,.jpg,.jpeg,.webp,.bmp';
  export let disabled = false;

  const dispatch = createEventDispatcher<{ files: File[] }>();

  function matchesAccept(file: File): boolean {
    const tokens = accept
      .split(',')
      .map((v) => v.trim().toLowerCase())
      .filter(Boolean);
    if (!tokens.length) return true;
    const name = file.name.toLowerCase();
    return tokens.some((ext) => (ext.startsWith('.') ? name.endsWith(ext) : true));
  }

  function publish(files: File[]): void {
    const allowed = files.filter((f) => matchesAccept(f));
    if (!allowed.length) return;
    dispatch('files', allowed);
  }

  async function collectFilesFromItems(items: DataTransferItemList | null): Promise<File[]> {
    if (!items) return [];
    const out: File[] = [];

    async function walkEntry(entry: any): Promise<void> {
      if (!entry) return;
      if (entry.isFile) {
        await new Promise<void>((resolve) => {
          entry.file((file: File) => {
            out.push(file);
            resolve();
          });
        });
        return;
      }
      if (entry.isDirectory) {
        const reader = entry.createReader();
        await new Promise<void>((resolve) => {
          const read = () => {
            reader.readEntries(async (entries: any[]) => {
              if (!entries || entries.length === 0) {
                resolve();
                return;
              }
              for (const child of entries) {
                await walkEntry(child);
              }
              read();
            });
          };
          read();
        });
      }
    }

    for (const item of Array.from(items)) {
      const anyItem = item as any;
      const entry = typeof anyItem.webkitGetAsEntry === 'function' ? anyItem.webkitGetAsEntry() : null;
      if (entry) {
        await walkEntry(entry);
        continue;
      }
      const file = item.getAsFile();
      if (file) out.push(file);
    }
    return out;
  }

  async function onDrop(event: DragEvent): Promise<void> {
    event.preventDefault();
    if (disabled) return;
    const fromItems = await collectFilesFromItems(event.dataTransfer?.items || null);
    const files = fromItems.length ? fromItems : Array.from(event.dataTransfer?.files || []);
    publish(files);
  }

  function onPick(event: Event): void {
    if (disabled) return;
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files || []);
    publish(files);
    input.value = '';
  }

  function openPicker(): void {
    if (disabled) return;
    const input = document.getElementById(inputId) as HTMLInputElement | null;
    input?.click();
  }
</script>

{#if visible}
  <div class="dz" id={id} class:disabled={disabled} role="button" tabindex="0" on:dragover|preventDefault on:drop={onDrop}>
    <div class="title">{label}</div>
    <button class="browse" type="button" on:click={openPicker} disabled={disabled}>Browse…</button>
    <input id={inputId} type="file" {accept} multiple on:change={onPick} />
    <div class="thumbs" id={thumbsId}>
      {#if !thumbnails.length}
        <span class="hint">No files selected</span>
      {:else}
        <span class="hint">{thumbnails.length} file(s) selected</span>
        {#each thumbnails as t}
          {#if t.startsWith('blob:') || t.startsWith('data:') || t.startsWith('http') || t.startsWith('/')}
            <img class="thumb" src={t} alt="preview" />
          {:else}
            <div class="pill">{t}</div>
          {/if}
        {/each}
      {/if}
    </div>
  </div>
{/if}

<style>
  .dz {
    border: 1px dashed #39537c;
    border-radius: 10px;
    padding: 12px;
    text-align: center;
    color: #9bb2d3;
    display: grid;
    gap: 8px;
    justify-items: center;
  }
  .dz.disabled {
    opacity: 0.55;
  }
  .title {
    font-size: 12px;
  }
  .browse {
    border: 1px solid #2f4a72;
    background: #13253f;
    color: #e7efff;
    border-radius: 8px;
    padding: 4px 9px;
    cursor: pointer;
    font-size: 12px;
  }
  .browse:disabled {
    cursor: default;
  }
  input[type='file'] {
    display: none;
  }
  .thumbs {
    margin-top: 2px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: center;
    width: 100%;
  }
  .hint {
    font-size: 11px;
    color: #8ba6cb;
  }
  .pill {
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 999px;
    border: 1px solid #2f4a72;
    color: #c6d7f3;
  }
  .thumb {
    width: 58px;
    height: 58px;
    object-fit: cover;
    border-radius: 7px;
    border: 1px solid #2f4a72;
    background: #081120;
  }
</style>
