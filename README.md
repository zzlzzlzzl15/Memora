# Memora Knowledge Graph v2.0.0

️ **Interactive knowledge graph visualization for your personal knowledge base**

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/zzlzzlzzl15/memora-knowledge-graph/releases/tag/v2.0.0)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![OpenCLAW Compatible](https://img.shields.io/badge/openclaw-compatible-orange.svg)](https://github.com/openclaw/openclaw)

## 🚀 Quick Start

### Install via clawhub (Coming Soon)
```bash
openclaw skill install memora-knowledge-graph@2.0.0
```

### Manual Installation
```bash
# Clone the repository
git clone https://github.com/zzlzzlzzl15/memora-knowledge-graph.git
cd memora-knowledge-graph

# Set environment variable
export KB_API_BASE=http://127.0.0.1:8080

# Start the server (optional, if you want to test standalone)
npm start
```

## ✨ Features

### Preview Cards
- **Compact Display**: Two small preview cards showing document and entity graphs
- **Non-interactive**: Read-only preview mode encourages click-to-expand
- **Hover Hint**: "Click to view full size" overlay on hover
- **Node Count Badge**: Shows total nodes in each graph

### Fullscreen Modal
- **Large Canvas**: 90vw × 85vh interactive visualization space
- **Zoom Control**: Mouse wheel zoom centered on cursor position (0.1x - 5x)
- **Pan/Drag**: Click and drag blank areas to move the entire graph
- **Node Drag**: Click and drag individual nodes to reposition
- **Hover Details**: Node labels appear on hover with glow effect
- **Refresh Button**: Reload current graph with latest data
- **Keyboard Support**: Press ESC to close modal

### Visual Design (Obsidian-Inspired)
- **Color Scheme**: Black nodes, white background, subtle gray connections
- **Glow Effect**: Multi-layer radial gradient on hover
- **Labels**: White background pill with black text
- **Force-Directed Layout**: Natural network structure with physics simulation

## 📦 Package Structure

```
memora-knowledge-graph/
├── static/
│   ├── index.html          # Main HTML page
│   ├── style.css           # All styles including KG components
│   ── script.js           # JavaScript with KnowledgeGraphVisualizer class
├── openclaw-skill/
│   ├── SKILL.md            # OpenCLAW skill definition
│   └── scripts/
│       └── kb_api.py       # API client script
├── package.json            # NPM package configuration
├── README.md               # This file
└── LICENSE                 # MIT license
```

##  Configuration

Set the `KB_API_BASE` environment variable to point to your Memora backend:

```bash
export KB_API_BASE=http://127.0.0.1:8080
```

Or create a `.env` file:
```
KB_API_BASE=http://127.0.0.1:8080
```

## 🎨 Customization

### Adjusting Force Parameters

Edit the `forceParams` in `static/script.js`:

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

## 🐛 Troubleshooting

### Issue: Preview cards not showing
**Solution**: Check browser console for errors. Ensure `initKnowledgeGraph()` is called after DOM ready.

### Issue: Nodes not centered
**Solution**: Hard refresh page (Cmd+Shift+R). Clear browser cache if needed.

### Issue: Cannot drag/zoom in modal
**Solution**: Verify `setInteractive(true)` is called for fullscreen visualizer. Check console logs.

### Issue: "Click to view" always visible
**Solution**: Ensure CSS has `opacity: 0 !important` and `visibility: hidden` for `.kg-preview-overlay`.

## 📊 Performance Tips

1. **Limit Node Count**: Use smaller limits for previews (50-80 nodes)
2. **Cache Data**: Reuse fetched data instead of reloading
3. **Debounce Resize**: Add debounce to window resize handler
4. **Reduce Iterations**: Lower `iterations` in `initForceLayout()` for faster load (default: 150)
5. **Optimize Rendering**: Skip rendering during rapid mouse movements

## 🌐 Browser Compatibility

- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

Requires:
- Canvas 2D API
- CSS backdrop-filter
- ES6+ JavaScript features

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by [Obsidian](https://obsidian.md/) graph view
- Built for [Memora](https://github.com/zzlzzlzzl15/Memora) personal knowledge base
- Uses force-directed layout algorithm similar to D3.js force simulation

##  Support

For issues and questions:
- GitHub Issues: https://github.com/zzlzzlzzl15/memora-knowledge-graph/issues
- Email: support@memora.dev

---

**Made with ❤️ by zzlzzlzzl15**
