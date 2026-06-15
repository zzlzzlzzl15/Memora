# 知识图谱可视化功能 - 完成! 🎉

## ✨ 新增功能

我已经成功在Memora前端**工作室(Studio)**区域添加了**知识图谱可视化**功能!

---

## 📋 功能特性

### 1. **入口位置**
- 📍 位于右侧"工作室"面板的第一个卡片
- 🏷️ 标题: "🕸️ 知识图谱"
- 📝 描述: "查看文档实体关系网络"

### 2. **可视化效果**
- 🎨 **力导向图布局** - 自动计算节点位置,自然分布
- 🌈 **彩色节点** - 不同类型实体使用不同颜色:
  - 👤 Person (人物): 红色 `#FF6B6B`
  - 🏢 Organization (组织): 青色 `#4ECDC4`
  - 📍 Location (地点): 绿色 `#95E1D3`
  - 💡 Concept (概念): 粉色 `#F38181`
  - 📅 Event (事件): 紫色 `#AA96DA`
  - 📦 Entity (通用): 蓝色 `#A8D8EA`

### 3. **交互功能**
- 🖱️ **拖拽节点** - 可以拖动任意节点调整位置
- 🔍 **缩放画布** - 鼠标滚轮放大/缩小
- ✋ **平移视图** - 拖拽空白区域移动整个图谱
- 💫 **悬停高亮** - 鼠标悬停节点时显示指针样式

### 4. **数据统计**
- 📊 左下角显示实时统计:
  - 节点数量 (总实体数)
  - 关系数量 (总连接数)

---

## 🚀 如何使用

### 步骤1: 访问Memora
打开浏览器访问: http://127.0.0.1:8000

### 步骤2: 登录账号
使用您的账号登录系统

### 步骤3: 点击知识图谱卡片
在右侧"工作室"面板中,点击第一个卡片 **"🕸️ 知识图谱"**

### 步骤4: 查看图谱
- 等待数据加载(显示loading动画)
- 图谱会自动渲染并运行动画
- 可以拖拽、缩放、平移来探索图谱

---

## 🔧 技术实现

### 后端API

#### 新增接口: `GET /api/v1/documents/knowledge-graph/full`

**功能**: 获取用户的完整知识图谱数据

**参数**:
- `limit` (可选): 最大节点数量,默认200,范围10-500

**返回格式**:
```json
{
  "nodes": [
    {
      "id": "entity_001",
      "label": "张三",
      "type": "Person",
      "description": "某公司员工"
    }
  ],
  "edges": [
    {
      "source": "entity_001",
      "target": "entity_002",
      "type": "WORKS_FOR",
      "weight": 1.0
    }
  ],
  "total_nodes": 50,
  "total_edges": 120
}
```

**实现位置**: 
- API: [app/api/documents.py](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/api/documents.py#L946-L967)
- Service: [app/services/knowledge_graph.py](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/services/knowledge_graph.py#L765-L836)

### 前端实现

#### 核心类: `KnowledgeGraphVisualizer`

**功能**:
- Canvas绘制力导向图
- 物理引擎模拟(斥力+引力)
- 交互事件处理(拖拽、缩放、平移)
- 动画渲染循环

**关键方法**:
- `loadData(data)` - 加载图谱数据
- `initForceLayout()` - 初始化力导向布局
- `render()` - 渲染图谱
- `startAnimation()` - 启动动画循环

**实现位置**: [static/script.js](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/static/script.js#L2917-L3246)

---

## 📁 修改的文件

### 后端文件
1. ✅ [app/services/knowledge_graph.py](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/services/knowledge_graph.py)
   - 添加 `get_full_graph()` 方法

2. ✅ [app/api/documents.py](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/api/documents.py)
   - 添加 `/knowledge-graph/full` API端点

### 前端文件
3. ✅ [static/index.html](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/static/index.html)
   - 添加知识图谱卡片
   - 添加模态框结构

4. ✅ [static/style.css](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/static/style.css)
   - 添加知识图谱模态框样式
   - 添加loading动画样式

5. ✅ [static/script.js](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/static/script.js)
   - 添加 `KnowledgeGraphVisualizer` 类
   - 添加 `initKnowledgeGraph()` 函数

---

## ⚠️ 注意事项

### 前置条件
1. **Neo4j必须运行** - 知识图谱数据存储在Neo4j数据库中
2. **必须有文档数据** - 需要先上传文档并提取实体
3. **实体提取已完成** - 文档处理时会异步提取实体到图谱

### 性能优化
- 默认限制返回200个节点(可调整)
- 力导向布局在客户端计算,避免服务器压力
- 使用Canvas渲染,性能优于SVG

### 已知限制
- 节点过多时(>500)可能导致页面卡顿
- 当前不支持点击节点查看详情(后续可扩展)
- 关系类型固定为RELATED_TO(可扩展更多类型)

---

## 🎯 测试建议

### 场景1: 空图谱
- 新用户或无文档数据
- 应显示"节点: 0 | 关系: 0"
- 画布为空,无错误

### 场景2: 少量节点(<50)
- 上传1-2个文档
- 图谱清晰可见,节点不重叠
- 可以流畅拖拽和缩放

### 场景3: 大量节点(50-200)
- 上传多个文档
- 图谱自动布局合理
- 性能依然流畅

### 场景4: 超大数据集(>200)
- 通过API参数限制节点数
- 只显示最近的200个实体
- 保证页面响应速度

---

## 🔮 未来扩展方向

1. **节点详情** - 点击节点显示详细信息
2. **关系过滤** - 按关系类型筛选显示
3. **搜索定位** - 搜索特定实体并高亮
4. **导出图片** - 将图谱导出为PNG/JPG
5. **时间轴** - 按时间展示图谱演化
6. **3D效果** - 使用Three.js实现3D可视化
7. **社区发现** - 自动识别并着色不同社群

---

## 📞 问题反馈

如果遇到问题,请检查:
1. Neo4j服务是否正常运行
2. 浏览器控制台是否有JavaScript错误
3. 网络请求是否成功(API返回200)
4. 是否有足够的文档数据生成图谱

---

**现在请访问 http://127.0.0.1:8000 体验知识图谱可视化功能!** 🕸️✨
