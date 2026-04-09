<script lang="ts">
  export let status = 'pending';
  const cls = (s: string): string => `s-${String(s || '').toLowerCase()}`;
</script>

<span class={`badge ${cls(status)}`}>
  <span class="dot"></span>
  <span>{status}</span>
</span>

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    border-radius: var(--radius-full);
    padding: 0.34rem 0.68rem;
    font-size: 0.73rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border: 1px solid var(--color-line);
    background: rgba(255, 255, 255, 0.04);
  }
  .dot {
    width: 0.45rem;
    height: 0.45rem;
    border-radius: 50%;
    background: currentColor;
    box-shadow: 0 0 0 0.2rem rgba(255, 255, 255, 0.03);
  }
  .s-running {
    color: var(--color-running);
    background: rgba(216, 161, 94, 0.12);
    border-color: rgba(216, 161, 94, 0.28);
  }
  .s-failed {
    color: var(--color-failed);
    background: rgba(216, 118, 134, 0.12);
    border-color: rgba(216, 118, 134, 0.28);
  }
  .s-pending {
    color: var(--color-pending);
    background: rgba(133, 167, 212, 0.12);
    border-color: rgba(133, 167, 212, 0.28);
  }
  .s-succeeded {
    color: var(--color-succeeded);
    background: rgba(125, 182, 147, 0.12);
    border-color: rgba(125, 182, 147, 0.28);
  }
  .s-canceled {
    color: var(--color-canceled);
    background: rgba(169, 155, 122, 0.12);
    border-color: rgba(169, 155, 122, 0.28);
  }
</style>
