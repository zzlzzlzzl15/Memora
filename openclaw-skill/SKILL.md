---
name: memora-knowledge-graph
description: >
  Memora Knowledge Graph — Interactive knowledge graph visualization for your personal knowledge base.
  Features document-entity relationship mapping with force-directed layout, zoom/pan/drag interactions,
  and Obsidian-style visual design (black nodes, white background, subtle connections).
  Use when: user wants to visualize relationships between documents and entities, explore knowledge structure,
  or understand how information is connected in their knowledge base.
metadata:
  version: 2.0.0
  author: zzlzzlzzl15
  license: MIT
  openclaw:
    requires:
      env:
        - KB_API_BASE
---

# Memora Knowledge Graph Visualization

Interactive knowledge graph visualization component for Memora personal knowledge base. Provides a visual representation of document-entity relationships with modern interaction patterns.

## Version History

### v2.0.0 (Current)
-  **New Feature**: Preview + Fullscreen Modal architecture
- 🎨 **UI Redesign**: Compact preview cards with click-to-expand fullscreen view
- 🖱️ **Enhanced Interaction**: Zoom (mouse wheel), pan (drag blank area), node drag, hover details
- 🎯 **Centered Layout**: Force-directed algorithm centers all nodes at origin
-  **Obsidian Style**: Black nodes, white background, subtle gray connections
- 🔄 **Smart Caching**: Preview data cached, modal uses larger dataset
- 📊 **Dual Views**: Separate document graph and entity graph views

### v1.0.0
- Initial release with basic knowledge graph visualization

## Features

### Preview Cards
- **Compact Display**: Two small preview cards (200px height) showing document and entity graphs
- **Non-interactive**: Preview mode is read-only, encourages click to expand
- **Hover Hint**: "Click to view full size" overlay appears on hover
- **Node Count Badge**: Shows total nodes in each graph

### Fullscreen Modal
- **Large Canvas**: 90vw × 85vh interactive visualization space
- **Zoom Control**: Mouse wheel zoom centered on cursor position (scale 0.1x - 5x)
- **Pan/Drag**: Click and drag blank areas to move the entire graph
- **Node Drag**: Click and drag individual nodes to reposition
- **Hover Details**: Node labels appear on hover with glow effect
- **Refresh Button**: Reload current graph with latest data
- **Keyboard Support**: Press ESC to close modal

### Visual Design
- **Color Scheme**: 
  - Background: White (#ffffff)
  - Nodes: Black (#000000) with gray border
  - Edges: Semi-transparent black lines (opacity based on weight)
- **Node Size**: Base radius 4px, scaled by label length (max 6px)
- **Glow Effect**: Multi-layer radial gradient on hover (Obsidian-inspired)
- **Labels**: White background pill with black text, positioned below nodes

### Layout Algorithm
- **Force-Directed**: Simulates physical forces between nodes
  - Repulsion: All nodes repel each other (prevents overlap)
  - Attraction: Connected nodes attract (spring-like edges)
  - Center Force: Pulls nodes toward center (prevents drift)
- **Initialization**: Circular distribution for even starting positions
- **Boundary Constraints**: Keeps nodes within visible canvas area
- **Damping**: Gradually reduces velocity for stable convergence

## Installation

### Option 1: Clone from clawhub
```bash
git clone https://github.com/zzlzzlzzl15/memora-knowledge-graph.git
cd memora-knowledge-graph
```

### Option 2: Download Release
```bash
curl -L https://github.com/zzlzzlzzl15/memora-knowledge-graph/releases/download/v2.0.0/memora-knowledge-graph-v2.0.0.tar.gz | tar xz
cd memora-knowledge-graph
```

### Option 3: Install via pip (if published)
```bash
pip install memora-knowledge-graph==2.0.0
```

## Configuration

Set the environment variable `KB_API_BASE` to point to your Memora backend:

```bash
export KB_API_BASE=http://127.0.0.1:8080
```

Or create a `.env` file:
```
KB_API_BASE=http://127.0.0.1:8080
```

## Usage

### Basic Setup

1. **Include HTML Structure**
   ```html
   <!-- Knowledge Graph Container -->
   <div id="kg-view-container">
       <!-- Document Graph Preview -->
       <div class="kg-preview-card" id="kg-docs-preview">
           <div class="kg-preview-header">
               <h3>📄 Document Graph</h3>
               <span class="kg-preview-badge" id="kg-docs-badge">0 nodes</span>
           </div>
           <div class="kg-preview-canvas">
               <canvas id="kg-canvas-docs-preview"></canvas>
               <div class="kg-preview-overlay">
                   <span class="preview-hint">Click to view full size</span>
               </div>
           </div>
       </div>
       
       <!-- Entity Graph Preview -->
       <div class="kg-preview-card" id="kg-entities-preview">
           <div class="kg-preview-header">
               <h3>🔵 Entity Graph</h3>
               <span class="kg-preview-badge" id="kg-entities-badge">0 nodes</span>
           </div>
           <div class="kg-preview-canvas">
               <canvas id="kg-canvas-entities-preview"></canvas>
               <div class="kg-preview-overlay">
                   <span class="preview-hint">Click to view full size</span>
               </div>
           </div>
       </div>
   </div>
   
   <!-- Fullscreen Modal -->
   <div id="kg-modal" class="kg-modal">
       <div class="kg-modal-content">
           <div class="kg-modal-header">
               <h3 id="kg-modal-title">Knowledge Graph</h3>
               <div class="kg-modal-controls">
                   <button id="kg-modal-refresh" class="kg-btn-icon" title="Refresh">
                       <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                           <path d="M23 4v6h-6M1 20v-6h6"/>
                           <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                       </svg>
                   </button>
                   <button id="kg-modal-close" class="kg-btn-icon" title="Close">
                       <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                           <line x1="18" y1="6" x2="6" y2="18"/>
                           <line x1="6" y1="6" x2="18" y2="18"/>
                       </svg>
                   </button>
               </div>
           </div>
           <div class="kg-modal-body">
               <canvas id="kg-canvas-fullscreen"></canvas>
               <div id="kg-modal-loading" class="kg-modal-loading">
                   <div class="spinner"></div>
                   <p>Loading...</p>
               </div>
           </div>
           <div class="kg-modal-footer">
               <div class="kg-modal-stats">
                   <span id="kg-modal-node-count">Nodes: 0</span>
                   <span id="kg-modal-edge-count">Edges: 0</span>
               </div>
               <div class="kg-modal-hints">
                   <span>🖱️ Scroll to zoom</span>
                   <span>✋ Drag to pan</span>
                   <span> Hover for details</span>
               </div>
           </div>
       </div>
   </div>
   ```

2. **Include CSS Stylesheet**
   ```html
   <link rel="stylesheet" href="/static/style.css?v=kg-panning-fix-20260613">
   ```

3. **Initialize JavaScript**
   ```javascript
   // Call after DOM is ready
   document.addEventListener('DOMContentLoaded', () => {
       initKnowledgeGraph();
   });
   ```

### API Integration

The knowledge graph automatically fetches data from these endpoints:

#### Document Graph
```
GET /api/v1/documents/knowledge-graph/documents?limit={n}
Headers: Authorization: Bearer {token}

Response:
{
  "nodes": [
    {"id": "doc_1", "label": "Document Title", "type": "Document"},
    ...
  ],
  "edges": [
    {"source": "doc_1", "target": "entity_a", "weight": 0.8},
    ...
  ],
  "total_nodes": 50,
  "total_edges": 120
}
```

#### Entity Graph
```
GET /api/v1/documents/knowledge-graph/entities?limit={n}
Headers: Authorization: Bearer {token}

Response: Same structure as above
```

### Data Loading Limits

- **Preview Mode**: 
  - Documents: 50 nodes max
  - Entities: 80 nodes max
  
- **Fullscreen Mode**:
  - Documents: 200 nodes max
  - Entities: 300 nodes max

## Customization

### Adjusting Force Parameters

Edit the `forceParams` in `script.js`:

```javascript
this.forceParams = {
    repulsion: 1200,        // Higher = more spread out
    attraction: 0.03,       // Higher = tighter clusters
    damping: 0.85,          // Lower = faster stabilization
    centerForce: 0.005,     // Higher = stronger pull to center
    maxVelocity: 8          // Cap on movement speed
};
```

### Changing Colors

Modify in `KnowledgeGraphVisualizer` constructor:

```javascript
// Node color (default: black)
this.nodeColor = '#000000';

// Edge opacity calculation (in render method)
const opacity = Math.min(0.3, 0.1 + weight * 0.05);
```

### Adjusting Node Sizes

Change base radius and scaling:

```javascript
baseRadius: 4,  // Minimum node size
radius: 4 + Math.min((node.label || '').length * 0.3, 6)  // Max additional 6px
```

## Troubleshooting

### Issue: Preview cards not showing
**Solution**: Check browser console for errors. Ensure `initKnowledgeGraph()` is called after DOM ready.

### Issue: Nodes not centered
**Solution**: Hard refresh page (Cmd+Shift+R). Clear browser cache if needed.

### Issue: Cannot drag/zoom in modal
**Solution**: Verify `setInteractive(true)` is called for fullscreen visualizer. Check console logs.

### Issue: "Click to view" always visible
**Solution**: Ensure CSS has `opacity: 0 !important` and `visibility: hidden` for `.kg-preview-overlay`.

### Issue: Graph looks squashed
**Solution**: Call `visualizer.resize()` after modal opens to recalculate canvas dimensions.

## Performance Tips

1. **Limit Node Count**: Use smaller limits for previews (50-80 nodes)
2. **Cache Data**: Reuse fetched data instead of reloading
3. **Debounce Resize**: Add debounce to window resize handler
4. **Reduce Iterations**: Lower `iterations` in `initForceLayout()` for faster load (default: 150)
5. **Optimize Rendering**: Skip rendering during rapid mouse movements

## Browser Compatibility

- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

Requires:
- Canvas 2D API
- CSS backdrop-filter
- ES6+ JavaScript features

## Dependencies

**No external dependencies!** Uses only:
- HTML5 Canvas 2D API
- Vanilla JavaScript (ES6+)
- CSS3 (with vendor prefixes where needed)

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues and questions:
- GitHub Issues: https://github.com/zzlzzlzzl15/memora-knowledge-graph/issues
- Email: support@memora.dev

## Acknowledgments

- Inspired by [Obsidian](https://obsidian.md/) graph view
- Built for [Memora](https://github.com/zzlzzlzzl15/Memora) personal knowledge base
- Uses force-directed layout algorithm similar to D3.js force simulation
