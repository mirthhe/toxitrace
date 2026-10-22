// 2D structure drawings, rendered in the browser with RDKit.js (the WebAssembly build of the
// same RDKit the backend uses). Rendering client-side keeps the backend free of RDKit's drawing
// libraries, which need system graphics libraries that serverless hosts do not provide.
import initRDKitModule, { type MainModule } from '@rdkit/rdkit'
import wasmUrl from '@rdkit/rdkit/RDKit_minimal.wasm?url'

let rdkit: Promise<MainModule> | null = null

function loadRDKit(): Promise<MainModule> {
  rdkit ??= initRDKitModule({ locateFile: () => wasmUrl })
  return rdkit
}

/** An SVG data URL for the structure, or null if RDKit cannot parse the SMILES. */
export async function depict(smiles: string, width: number, height: number): Promise<string | null> {
  const RDKit = await loadRDKit()
  const mol = RDKit.get_mol(smiles)
  if (!mol) return null
  try {
    const svg = mol.get_svg_with_highlights(
      JSON.stringify({ width, height, clearBackground: false, bondLineWidth: 1.5 }),
    )
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
  } finally {
    mol.delete()
  }
}
