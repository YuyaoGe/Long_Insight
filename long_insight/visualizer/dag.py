#!/usr/bin/env python3
"""
Interactive DAG visualization for trajectory step analysis.

Converts step analysis JSON into an interactive HTML page with:
- Zoomable, draggable DAG layout
- Step type color coding
- Click-to-expand detail panels
- Search and filter controls

Supports both English field names (from Long-Insight) and legacy Chinese field names.
"""

import json
import argparse
import os
from typing import Dict, List, Any, Union


def load_steps(json_file: str) -> List[Dict]:
    """Load step analysis JSON file."""
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_parent_ids(parent_field: Union[int, List[int], None]) -> List[int]:
    """Normalize parent field to a list of ints."""
    if parent_field is None:
        return [-1]
    if isinstance(parent_field, list):
        return parent_field if parent_field else [-1]
    return [parent_field]


def _get(step: Dict, en_key: str, cn_key: str, default=None):
    """Get a field supporting both English and Chinese keys."""
    return step.get(en_key, step.get(cn_key, default))


def build_graph_data(steps: List[Dict]) -> Dict:
    """Convert step list into DAG structure (supports multi-parent nodes)."""
    nodes = []
    links = []
    root_ids = []

    node_by_id = {}
    children_map = {}
    parents_map = {}

    for step in steps:
        step_id = _get(step, "id", "当前步骤的编号", 0)
        parent_ids = normalize_parent_ids(
            _get(step, "parent_ids", "当前步骤的父亲行为")
        )

        node = {
            "id": step_id,
            "type": _get(step, "type", "当前步骤类型", "unknown"),
            "title": _get(step, "title", "当前步骤的标题", f"Step {step_id}"),
            "start_turn": _get(step, "start_turn", "当前步骤的起始轮数", 0),
            "end_turn": _get(step, "end_turn", "当前步骤的结束轮数", 0),
            "summary": _get(step, "summary", "当前步骤的摘要", ""),
            "detail": _get(step, "detail", "当前步骤的详细操作", ""),
            "parent_ids": parent_ids,
            "depth": 0
        }
        nodes.append(node)
        node_by_id[step_id] = node

        # 检查是否为根节点
        is_root = len(parent_ids) == 1 and parent_ids[0] == -1
        if is_root:
            root_ids.append(step_id)
        else:
            # 为每个父节点创建一条边
            for parent_id in parent_ids:
                if parent_id != -1:
                    links.append({
                        "source": parent_id,
                        "target": step_id
                    })
                    # 构建邻接表
                    if parent_id not in children_map:
                        children_map[parent_id] = []
                    children_map[parent_id].append(step_id)
                    if step_id not in parents_map:
                        parents_map[step_id] = []
                    parents_map[step_id].append(parent_id)
    
    # 第二遍：计算深度（使用拓扑排序）
    # 按ID排序处理（因为数据是按顺序生成的，ID小的先处理）
    sorted_ids = sorted(node_by_id.keys())
    
    for node_id in sorted_ids:
        node = node_by_id[node_id]
        parents = parents_map.get(node_id, [])
        
        if not parents or (len(node["parent_ids"]) == 1 and node["parent_ids"][0] == -1):
            # 根节点
            node["depth"] = 0
        else:
            # 深度 = 所有父节点的最大深度 + 1
            max_parent_depth = 0
            for pid in parents:
                if pid in node_by_id:
                    max_parent_depth = max(max_parent_depth, node_by_id[pid]["depth"])
            node["depth"] = max_parent_depth + 1
    
    # 第三遍：计算跨层连接信息和偏移量
    cross_layer_count = 0
    for node in nodes:
        node["hasCrossLayer"] = False
        node["yOffset"] = 0
        
    for node_id in sorted_ids:
        node = node_by_id[node_id]
        parents = parents_map.get(node_id, [])
        
        # 检查是否有跨层父节点
        cross_layer_parents = []
        direct_parents = []
        for pid in parents:
            if pid in node_by_id:
                depth_diff = node["depth"] - node_by_id[pid]["depth"]
                if depth_diff > 1:
                    cross_layer_parents.append(pid)
                    cross_layer_count += 1
                elif depth_diff == 1:
                    direct_parents.append(pid)
        
        if cross_layer_parents:
            node["hasCrossLayer"] = True
            # 计算偏移方向：如果跨层父节点的索引较小，向下偏移；否则向上
            # 这样可以让跨层连线更清晰
            cross_avg = sum(node_by_id[p]["depth"] for p in cross_layer_parents) / len(cross_layer_parents)
            direct_avg = sum(node_by_id[p]["depth"] for p in direct_parents) / len(direct_parents) if direct_parents else cross_avg
            
            # 偏移量：跨层越多，偏移越大
            max_cross_depth = max(node["depth"] - node_by_id[p]["depth"] for p in cross_layer_parents)
            offset_factor = min(max_cross_depth * 0.15, 0.5)  # 最多偏移50%的节点间距
            node["yOffset"] = offset_factor if cross_avg < direct_avg else -offset_factor
    
    print(f"跨层连接数: {cross_layer_count}")
    
    # 输出深度统计
    depth_count = {}
    for node in nodes:
        d = node["depth"]
        depth_count[d] = depth_count.get(d, 0) + 1
    print(f"深度分布: {dict(sorted(depth_count.items()))}")
    print(f"最大深度: {max(depth_count.keys())}")

    return {
        "nodes": nodes,
        "links": links,
        "root_ids": root_ids,
        "total_steps": len(steps)
    }


def generate_html(graph_data: Dict, output_file: str, title: str = "步骤可视化"):
    """生成HTML可视化文件"""

    html_template = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #e0e0e0;
            overflow: hidden;
        }}

        .header {{
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            padding: 15px 30px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 100;
        }}

        .header h1 {{
            font-size: 20px;
            font-weight: 600;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .stats {{
            display: flex;
            gap: 15px;
        }}

        .stat-item {{
            background: rgba(255, 255, 255, 0.05);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 13px;
        }}

        .stat-item span {{
            color: #667eea;
            font-weight: 600;
        }}

        #graph-container {{
            position: fixed;
            top: 60px;
            left: 0;
            right: 0;
            bottom: 0;
            overflow: hidden;
        }}

        #graph {{
            width: 100%;
            height: 100%;
            cursor: grab;
        }}

        #graph:active {{
            cursor: grabbing;
        }}

        /* 悬停提示框 */
        .tooltip {{
            position: fixed;
            background: rgba(30, 30, 50, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(102, 126, 234, 0.5);
            border-radius: 8px;
            padding: 12px 15px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
            max-width: 350px;
            z-index: 1000;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }}

        .tooltip.visible {{
            opacity: 1;
        }}

        .tooltip-title {{
            font-weight: 600;
            font-size: 14px;
            color: #667eea;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .tooltip-title .step-num {{
            background: #667eea;
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
        }}

        .tooltip-type {{
            font-size: 11px;
            color: #888;
            margin-bottom: 8px;
        }}

        .tooltip-summary {{
            font-size: 12px;
            color: #ccc;
            line-height: 1.5;
        }}

        /* 详情弹窗 */
        .modal-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 2000;
        }}

        .modal-overlay.visible {{
            display: flex;
        }}

        .modal {{
            background: linear-gradient(135deg, #1e1e30 0%, #252540 100%);
            border: 1px solid rgba(102, 126, 234, 0.3);
            border-radius: 12px;
            max-width: 700px;
            max-height: 80vh;
            width: 90%;
            overflow: hidden;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
        }}

        .modal-header {{
            background: rgba(102, 126, 234, 0.1);
            padding: 20px 25px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }}

        .modal-header-left {{
            display: flex;
            align-items: center;
            gap: 15px;
        }}

        .modal-step-num {{
            width: 45px;
            height: 45px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 18px;
        }}

        .modal-title-group h2 {{
            font-size: 18px;
            margin-bottom: 5px;
        }}

        .modal-type {{
            font-size: 12px;
            color: #667eea;
            background: rgba(102, 126, 234, 0.15);
            padding: 3px 10px;
            border-radius: 4px;
            display: inline-block;
        }}

        .modal-close {{
            background: none;
            border: none;
            color: #888;
            font-size: 28px;
            cursor: pointer;
            padding: 0;
            line-height: 1;
        }}

        .modal-close:hover {{
            color: #fff;
        }}

        .modal-body {{
            padding: 25px;
            overflow-y: auto;
            max-height: calc(80vh - 100px);
        }}

        .modal-info-row {{
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}

        .modal-info-item {{
            background: rgba(255, 255, 255, 0.05);
            padding: 10px 15px;
            border-radius: 6px;
            font-size: 13px;
        }}

        .modal-info-item label {{
            color: #888;
            display: block;
            margin-bottom: 3px;
            font-size: 11px;
        }}

        .modal-info-item span {{
            color: #667eea;
            font-weight: 600;
        }}

        .modal-section {{
            margin-bottom: 20px;
        }}

        .modal-section:last-child {{
            margin-bottom: 0;
        }}

        .modal-section h4 {{
            font-size: 12px;
            color: #888;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .modal-section p {{
            font-size: 14px;
            line-height: 1.7;
            color: #ccc;
            background: rgba(0, 0, 0, 0.2);
            padding: 15px;
            border-radius: 8px;
            white-space: pre-wrap;
        }}

        /* 控制按钮 */
        .controls {{
            position: fixed;
            bottom: 20px;
            left: 20px;
            display: flex;
            gap: 8px;
            z-index: 100;
            flex-wrap: wrap;
            max-width: 500px;
        }}

        .control-btn {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: #fff;
            padding: 8px 14px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        }}

        .control-btn:hover {{
            background: rgba(255, 255, 255, 0.2);
        }}

        .control-btn.active {{
            background: rgba(102, 126, 234, 0.4);
            border-color: #667eea;
        }}
        
        /* 间距控制面板 */
        .spacing-control {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(10px);
            padding: 15px;
            border-radius: 8px;
            z-index: 100;
            min-width: 250px;
            display: none;
        }}
        
        .spacing-control.visible {{
            display: block;
        }}
        
        .spacing-control h3 {{
            margin: 0 0 12px 0;
            font-size: 13px;
            color: #667eea;
        }}
        
        .spacing-item {{
            margin-bottom: 12px;
        }}
        
        .spacing-item label {{
            display: block;
            font-size: 11px;
            color: #888;
            margin-bottom: 5px;
        }}
        
        .spacing-item input[type="range"] {{
            width: 100%;
            height: 4px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 2px;
            outline: none;
        }}
        
        .spacing-item input[type="range"]::-webkit-slider-thumb {{
            width: 14px;
            height: 14px;
            background: #667eea;
            border-radius: 50%;
            cursor: pointer;
        }}
        
        .spacing-value {{
            display: inline-block;
            float: right;
            color: #667eea;
            font-weight: 600;
        }}
        
        /* 搜索框 */
        .search-box {{
            position: fixed;
            top: 80px;
            right: 20px;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(10px);
            padding: 10px 15px;
            border-radius: 8px;
            z-index: 100;
            width: 250px;
        }}
        
        .search-box input {{
            width: 100%;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 8px 12px;
            border-radius: 6px;
            color: #fff;
            font-size: 13px;
            outline: none;
        }}
        
        .search-box input:focus {{
            border-color: #667eea;
        }}
        
        .search-box input::placeholder {{
            color: #666;
        }}
        
        .search-results {{
            margin-top: 8px;
            max-height: 200px;
            overflow-y: auto;
        }}
        
        .search-result-item {{
            padding: 6px 8px;
            cursor: pointer;
            border-radius: 4px;
            font-size: 12px;
            margin-bottom: 2px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .search-result-item:hover {{
            background: rgba(255, 255, 255, 0.1);
        }}
        
        .search-result-item .step-id {{
            background: #667eea;
            color: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
        }}

        /* 图例 */
        .legend {{
            position: fixed;
            top: 80px;
            left: 20px;
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(10px);
            padding: 12px 15px;
            border-radius: 8px;
            font-size: 11px;
            z-index: 100;
            max-height: calc(100vh - 200px);
            overflow-y: auto;
        }}

        .legend-title {{
            font-weight: 600;
            margin-bottom: 8px;
            color: #888;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 5px;
            cursor: pointer;
            padding: 2px 4px;
            border-radius: 4px;
        }}

        .legend-item:hover {{
            background: rgba(255, 255, 255, 0.1);
        }}

        .legend-item:last-child {{
            margin-bottom: 0;
        }}

        .legend-color {{
            width: 14px;
            height: 14px;
            border-radius: 3px;
            flex-shrink: 0;
        }}

        .legend-count {{
            color: #666;
            margin-left: auto;
        }}

        /* 节点样式 */
        .node {{
            cursor: grab;
        }}

        .node.dragging {{
            cursor: grabbing;
        }}

        .node rect {{
            stroke-width: 2px;
            transition: filter 0.15s;
        }}

        .node:hover rect {{
            filter: brightness(1.3);
        }}

        .node.highlighted rect {{
            stroke: #fff !important;
            stroke-width: 3px;
            filter: brightness(1.3);
        }}

        .node.dimmed {{
            opacity: 0.15;
        }}

        .node.dimmed rect {{
            filter: none;
        }}

        .node text {{
            fill: #fff;
            pointer-events: none;
            user-select: none;
        }}

        /* 线条样式优化 */
        .link {{
            fill: none;
            stroke: rgba(102, 126, 234, 0.15);
            stroke-width: 1.5px;
            transition: stroke 0.2s, stroke-width 0.2s, opacity 0.2s;
        }}

        .link.highlighted {{
            stroke: #667eea;
            stroke-width: 3px;
            opacity: 1;
        }}

        .link.dimmed {{
            opacity: 0.05;
        }}

        /* 多父节点标记 */
        .multi-parent-indicator {{
            fill: #ffc107;
            font-size: 10px;
        }}

        /* 提示信息 */
        .hint {{
            position: fixed;
            bottom: 70px;
            left: 20px;
            background: rgba(0, 0, 0, 0.5);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 11px;
            color: #888;
            z-index: 100;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <div class="stats">
            <div class="stat-item">总步骤: <span>{total_steps}</span></div>
            <div class="stat-item">根节点: <span>{root_count}</span></div>
            <div class="stat-item">连接数: <span>{link_count}</span></div>
        </div>
    </div>

    <div id="graph-container">
        <svg id="graph"></svg>
    </div>

    <div class="tooltip" id="tooltip"></div>

    <div class="modal-overlay" id="modal-overlay">
        <div class="modal">
            <div class="modal-header">
                <div class="modal-header-left">
                    <div class="modal-step-num" id="modal-num">1</div>
                    <div class="modal-title-group">
                        <h2 id="modal-title">步骤标题</h2>
                        <span class="modal-type" id="modal-type">类型</span>
                    </div>
                </div>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="modal-info-row">
                    <div class="modal-info-item">
                        <label>起始轮数</label>
                        <span id="modal-start">1</span>
                    </div>
                    <div class="modal-info-item">
                        <label>结束轮数</label>
                        <span id="modal-end">1</span>
                    </div>
                    <div class="modal-info-item">
                        <label>父节点</label>
                        <span id="modal-parent">-1</span>
                    </div>
                </div>
                <div class="modal-section">
                    <h4>摘要</h4>
                    <p id="modal-summary">步骤摘要</p>
                </div>
                <div class="modal-section">
                    <h4>详细操作</h4>
                    <p id="modal-detail">详细操作</p>
                </div>
            </div>
        </div>
    </div>

    <div class="legend" id="legend">
        <div class="legend-title">步骤类型</div>
    </div>

    <div class="search-box">
        <input type="text" id="search-input" placeholder="搜索步骤（编号或标题）..." oninput="searchNodes()">
        <div class="search-results" id="search-results"></div>
    </div>

    <div class="hint">拖拽节点可移动位置 | 悬停节点高亮相关连线 | 点击查看详情 | 滚轮缩放</div>

    <div class="controls">
        <button class="control-btn" onclick="zoomIn()">放大 +</button>
        <button class="control-btn" onclick="zoomOut()">缩小 -</button>
        <button class="control-btn" onclick="resetView()">重置视图</button>
        <button class="control-btn" onclick="resetPositions()">重置位置</button>
        <button class="control-btn" onclick="toggleLayout()">切换布局</button>
        <button class="control-btn" id="spacing-toggle" onclick="toggleSpacingPanel()">调整间距</button>
    </div>
    
    <div class="spacing-control" id="spacing-panel">
        <h3>布局间距调整</h3>
        <div class="spacing-item">
            <label>
                层间距: <span class="spacing-value" id="layer-gap-value">250</span>
            </label>
            <input type="range" id="layer-gap" min="100" max="500" value="250" oninput="updateSpacing()">
        </div>
        <div class="spacing-item">
            <label>
                节点间距: <span class="spacing-value" id="node-gap-value">70</span>
            </label>
            <input type="range" id="node-gap" min="30" max="150" value="70" oninput="updateSpacing()">
        </div>
        <div class="spacing-item">
            <button class="control-btn" onclick="applySpacing()" style="width: 100%; margin-top: 5px;">应用</button>
        </div>
    </div>

    <script>
        // 数据
        const graphData = {graph_data_json};

        // 颜色映射
        const colorMap = {{
            "任务理解": "#667eea",
            "项目探索": "#28a745",
            "环境准备": "#ffc107",
            "测试验证": "#17a2b8",
            "代码实现": "#dc3545",
            "代码修复": "#e83e8c",
            "文档记录": "#6f42c1",
            "总结规划": "#fd7e14",
            "问题解决": "#20c997",
            "调试分析": "#6610f2",
            "错误处理": "#ff6b6b",
            "功能完善": "#4ecdc4",
            "默认": "#6c757d"
        }};

        // 全局状态
        let svg, mainGroup, linksGroup, nodesGroup, defsGroup;
        let allNodes = [];
        let allLinks = [];
        let isHorizontal = true;

        const nodeWidth = 180;
        const nodeHeight = 60;

        // 布局参数（可调整）
        let customLayerGap = null;
        let customNodeGap = null;

        // 缩放和平移状态
        let scale = 1;
        let translateX = 0;
        let translateY = 0;
        let isPanning = false;
        let startX, startY;

        // 节点拖拽状态
        let isDraggingNode = false;
        let draggedNode = null;
        let dragStartX, dragStartY;
        let nodeStartX, nodeStartY;

        // 初始化
        function init() {{
            const container = document.getElementById('graph-container');
            const width = container.clientWidth;
            const height = container.clientHeight;

            svg = document.getElementById('graph');
            svg.setAttribute('width', width);
            svg.setAttribute('height', height);

            // 清空SVG
            svg.innerHTML = '';

            // 创建defs用于箭头等
            defsGroup = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            svg.appendChild(defsGroup);

            // 创建箭头标记
            const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
            marker.setAttribute('id', 'arrowhead');
            marker.setAttribute('markerWidth', '10');
            marker.setAttribute('markerHeight', '7');
            marker.setAttribute('refX', '9');
            marker.setAttribute('refY', '3.5');
            marker.setAttribute('orient', 'auto');
            const arrowPath = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
            arrowPath.setAttribute('points', '0 0, 10 3.5, 0 7');
            arrowPath.setAttribute('fill', 'rgba(102, 126, 234, 0.4)');
            marker.appendChild(arrowPath);
            defsGroup.appendChild(marker);

            // 高亮箭头
            const markerHighlight = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
            markerHighlight.setAttribute('id', 'arrowhead-highlight');
            markerHighlight.setAttribute('markerWidth', '10');
            markerHighlight.setAttribute('markerHeight', '7');
            markerHighlight.setAttribute('refX', '9');
            markerHighlight.setAttribute('refY', '3.5');
            markerHighlight.setAttribute('orient', 'auto');
            const arrowPathHighlight = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
            arrowPathHighlight.setAttribute('points', '0 0, 10 3.5, 0 7');
            arrowPathHighlight.setAttribute('fill', '#667eea');
            markerHighlight.appendChild(arrowPathHighlight);
            defsGroup.appendChild(markerHighlight);

            // 创建主组
            mainGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            svg.appendChild(mainGroup);

            // 处理数据
            processData();

            // 绘制图形
            drawGraph();

            // 生成图例
            generateLegend();

            // 初始化缩放和拖拽
            initZoomPan();

            // 延迟适应屏幕
            setTimeout(fitToScreen, 100);
        }}

        function processData() {{
            // 直接使用预计算的节点数据（depth和yOffset已在Python中计算）
            allNodes = graphData.nodes.map(n => ({{
                ...n,
                depth: n.depth || 0,
                yOffset: n.yOffset || 0,  // 跨层连接的偏移量
                hasCrossLayer: n.hasCrossLayer || false,
                lane: 0,
                originalX: 0,
                originalY: 0
            }}));
            allLinks = graphData.links;

            console.log('节点数:', allNodes.length);
            const crossLayerNodes = allNodes.filter(n => n.hasCrossLayer).length;
            console.log('有跨层连接的节点数:', crossLayerNodes);
        }}

        function calculatePositions() {{
            // 按深度分层
            const layers = {{}};
            allNodes.forEach(node => {{
                if (!layers[node.depth]) layers[node.depth] = [];
                layers[node.depth].push(node);
            }});

            // 构建节点映射和邻接关系
            const nodeById = {{}};
            const parentsMap = {{}};
            const childrenMap = {{}};
            
            allNodes.forEach(n => nodeById[n.id] = n);
            allLinks.forEach(link => {{
                if (!childrenMap[link.source]) childrenMap[link.source] = [];
                childrenMap[link.source].push(link.target);
                if (!parentsMap[link.target]) parentsMap[link.target] = [];
                parentsMap[link.target].push(link.source);
            }});

            // 计算最大深度
            const maxDepth = Math.max(...allNodes.map(n => n.depth));
            console.log('最大深度:', maxDepth);
            
            // 计算每层的节点数
            let maxLayerSize = 0;
            Object.values(layers).forEach(layer => {{
                maxLayerSize = Math.max(maxLayerSize, layer.length);
            }});
            console.log('最大层节点数:', maxLayerSize);
            
            // 计算布局参数
            const totalNodes = allNodes.length;
            let baseLayerGap, baseNodeGap;
            
            if (customLayerGap !== null && customNodeGap !== null) {{
                baseLayerGap = customLayerGap;
                baseNodeGap = customNodeGap;
            }} else {{
                if (isHorizontal) {{
                    // 水平布局：根据深度动态调整层间距
                    if (maxDepth > 150) {{
                        baseLayerGap = 200;
                    }} else if (maxDepth > 100) {{
                        baseLayerGap = 210;
                    }} else if (maxDepth > 50) {{
                        baseLayerGap = 230;
                    }} else {{
                        baseLayerGap = 260;
                    }}
                    baseNodeGap = maxLayerSize > 6 ? 75 : 85;
                }} else {{
                    baseLayerGap = maxDepth > 100 ? 100 : 130;
                    baseNodeGap = 200;
                }}
            }}

            // === 改进的布局算法：考虑多父节点的跨层连接 ===
            const layerDepths = Object.keys(layers).map(d => parseInt(d)).sort((a, b) => a - b);
            
            // 第一遍：初始化层索引，按ID排序保持稳定
            layerDepths.forEach(depth => {{
                const layer = layers[depth];
                layer.sort((a, b) => a.id - b.id);
                layer.forEach((node, i) => {{
                    node.layerIndex = i;
                    node.targetY = i;  // 目标Y位置（用于后续优化）
                }});
            }});
            
            // 计算每个节点的"跨层父节点"信息
            // 跨层父节点 = 深度差 > 1 的父节点
            allNodes.forEach(node => {{
                const parents = parentsMap[node.id] || [];
                node.crossLayerParents = parents.filter(pid => {{
                    const parent = nodeById[pid];
                    return parent && (node.depth - parent.depth) > 1;
                }});
                node.hasCrossLayerEdge = node.crossLayerParents.length > 0;
            }});
            
            // 多次迭代优化
            for (let iter = 0; iter < 8; iter++) {{
                // 自顶向下传递
                for (let i = 1; i < layerDepths.length; i++) {{
                    const depth = layerDepths[i];
                    const layer = layers[depth];
                    
                    layer.forEach(node => {{
                        const parents = parentsMap[node.id] || [];
                        if (parents.length > 0) {{
                            // 计算所有父节点的位置
                            const parentPositions = parents.map(pid => {{
                                const parent = nodeById[pid];
                                if (!parent) return 0;
                                // 跨层父节点权重更高，避免连线被遮挡
                                const depthDiff = node.depth - parent.depth;
                                const weight = depthDiff > 1 ? 1.5 : 1.0;
                                return {{ pos: parent.layerIndex, weight }};
                            }});
                            
                            // 加权平均计算重心
                            const totalWeight = parentPositions.reduce((sum, p) => sum + p.weight, 0);
                            node.barycenter = parentPositions.reduce((sum, p) => sum + p.pos * p.weight, 0) / totalWeight;
                    
                            // 如果有跨层父节点，添加一个小偏移以错开位置
                            if (node.hasCrossLayerEdge) {{
                                // 偏移方向基于跨层父节点的位置
                                const crossParentAvg = node.crossLayerParents.reduce((sum, pid) => {{
                                    return sum + (nodeById[pid]?.layerIndex || 0);
                                }}, 0) / node.crossLayerParents.length;
                                
                                // 如果跨层父节点在上方（索引较小），则向下偏移，反之向上
                                const directParents = parents.filter(pid => {{
                                    const p = nodeById[pid];
                                    return p && (node.depth - p.depth) === 1;
                                }});
                                if (directParents.length > 0) {{
                                    const directAvg = directParents.reduce((sum, pid) => {{
                                        return sum + (nodeById[pid]?.layerIndex || 0);
                                    }}, 0) / directParents.length;
                                    
                                    // 偏移方向：远离直接父节点，让跨层连线更明显
                                    const offset = crossParentAvg < directAvg ? -0.3 : 0.3;
                                    node.barycenter += offset;
                                }}
                            }}
                        }} else {{
                            node.barycenter = node.layerIndex;
                    }}
                }});
                    
                    // 按重心排序
                    layer.sort((a, b) => (a.barycenter || 0) - (b.barycenter || 0));
                    layer.forEach((node, idx) => node.layerIndex = idx);
        }}

                // 自底向上传递
                for (let i = layerDepths.length - 2; i >= 0; i--) {{
                    const depth = layerDepths[i];
                    const layer = layers[depth];
                    
                    layer.forEach(node => {{
                        const children = childrenMap[node.id] || [];
                        if (children.length > 0) {{
                            // 计算子节点位置，考虑跨层连接
                            const childPositions = children.map(cid => {{
                                const child = nodeById[cid];
                                if (!child) return {{ pos: 0, weight: 1 }};
                                const depthDiff = child.depth - node.depth;
                                const weight = depthDiff > 1 ? 1.5 : 1.0;
                                return {{ pos: child.layerIndex, weight }};
            }});

                            const totalWeight = childPositions.reduce((sum, p) => sum + p.weight, 0);
                            node.barycenter = childPositions.reduce((sum, p) => sum + p.pos * p.weight, 0) / totalWeight;
                        }}
                    }});
                    
                    layer.sort((a, b) => (a.barycenter || 0) - (b.barycenter || 0));
                    layer.forEach((node, idx) => node.layerIndex = idx);
                }}
            }}

            // === 计算跨层连接的偏移量 ===
            // 对于有跨层连接的节点，需要在垂直方向上偏移，避免连线被中间节点遮挡
            
            // 首先，找出所有跨层连接
            const crossLayerEdges = [];
            allLinks.forEach(link => {{
                const source = nodeById[link.source];
                const target = nodeById[link.target];
                if (source && target) {{
                    const depthDiff = target.depth - source.depth;
                    if (depthDiff > 1) {{
                        crossLayerEdges.push({{
                            source: link.source,
                            target: link.target,
                            sourceDepth: source.depth,
                            targetDepth: target.depth
                        }});
                    }}
                }}
            }});
            
            console.log('跨层连接数:', crossLayerEdges.length);
            
            // 计算每个节点的偏移量
            allNodes.forEach(node => {{
                node.yOffset = 0;
            }});
            
            // 对于每个跨层连接，检查中间层的节点，并给目标节点添加偏移
            crossLayerEdges.forEach(edge => {{
                const source = nodeById[edge.source];
                const target = nodeById[edge.target];
                
                // 检查中间层是否有节点可能遮挡连线
                let hasBlockingNode = false;
                for (let d = edge.sourceDepth + 1; d < edge.targetDepth; d++) {{
                    const midLayer = layers[d];
                    if (midLayer) {{
                        midLayer.forEach(midNode => {{
                            // 如果中间节点的layerIndex与源节点相近，可能会遮挡
                            if (Math.abs(midNode.layerIndex - source.layerIndex) < 1) {{
                                hasBlockingNode = true;
                            }}
                        }});
                    }}
                }}
                
                if (hasBlockingNode) {{
                    // 给目标节点添加偏移，方向根据源节点位置决定
                    // 如果源节点在上方，目标节点向下偏移；反之向上
                    const offsetDirection = source.layerIndex <= target.layerIndex ? 1 : -1;
                    // 存储偏移系数（会在后面乘以baseNodeGap）
                    target.yOffset = offsetDirection * 0.4;
                }}
            }});

            // 应用位置（包含预计算的跨层偏移）
            layerDepths.forEach(depth => {{
                const layer = layers[depth];
                const layerSize = layer.length * baseNodeGap;
                const startOffset = -layerSize / 2 + baseNodeGap / 2;

                layer.forEach((node, i) => {{
                    // 使用预计算的yOffset（来自Python）
                    const precomputedOffset = (node.yOffset || 0) * baseNodeGap;
                    
                    if (isHorizontal) {{
                        node.x = parseInt(depth) * baseLayerGap + 100;
                        node.y = startOffset + i * baseNodeGap + precomputedOffset;
                    }} else {{
                        node.x = startOffset + i * baseNodeGap + precomputedOffset;
                        node.y = parseInt(depth) * baseLayerGap + 100;
                    }}
                    node.originalX = node.x;
                    node.originalY = node.y;
                }});
            }});
        }}

        function drawGraph() {{
            mainGroup.innerHTML = '';

            // 计算初始位置
            calculatePositions();

            // 创建节点映射
            const nodeById = {{}};
            allNodes.forEach(n => nodeById[n.id] = n);

            // 绘制连线
            linksGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            linksGroup.setAttribute('class', 'links-group');
            mainGroup.appendChild(linksGroup);

            allLinks.forEach((link, idx) => {{
                const source = nodeById[link.source];
                const target = nodeById[link.target];
                if (!source || !target) return;

                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('class', 'link');
                path.setAttribute('data-source', link.source);
                path.setAttribute('data-target', link.target);
                path.setAttribute('data-index', idx);
                path.setAttribute('marker-end', 'url(#arrowhead)');

                updateLinkPath(path, source, target);
                linksGroup.appendChild(path);
            }});

            // 绘制节点
            nodesGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            nodesGroup.setAttribute('class', 'nodes-group');
            mainGroup.appendChild(nodesGroup);

            allNodes.forEach(node => {{
                const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                g.setAttribute('class', 'node');
                g.setAttribute('transform', `translate(${{node.x}}, ${{node.y}})`);
                g.setAttribute('data-id', node.id);

                // 背景矩形
                const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                rect.setAttribute('width', nodeWidth);
                rect.setAttribute('height', nodeHeight);
                rect.setAttribute('rx', 6);
                rect.setAttribute('ry', 6);
                const color = colorMap[node.type] || colorMap['默认'];
                rect.setAttribute('fill', color);
                rect.setAttribute('stroke', shadeColor(color, -20));
                g.appendChild(rect);

                // 步骤编号
                const numText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                numText.setAttribute('x', 12);
                numText.setAttribute('y', 22);
                numText.setAttribute('font-size', '13px');
                numText.setAttribute('font-weight', 'bold');
                numText.textContent = '#' + node.id;
                g.appendChild(numText);

                // 多父节点指示器
                if (node.parent_ids && node.parent_ids.length > 1) {{
                    const indicator = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    indicator.setAttribute('class', 'multi-parent-indicator');
                    indicator.setAttribute('x', 50);
                    indicator.setAttribute('y', 22);
                    indicator.textContent = '⬥' + node.parent_ids.length;
                    g.appendChild(indicator);
                }}

                // 标题
                const titleText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                titleText.setAttribute('x', 12);
                titleText.setAttribute('y', 42);
                titleText.setAttribute('font-size', '12px');
                const title = node.title.length > 18 ? node.title.substring(0, 18) + '...' : node.title;
                titleText.textContent = title;
                g.appendChild(titleText);

                // 轮数
                const turnText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                turnText.setAttribute('x', nodeWidth - 10);
                turnText.setAttribute('y', 22);
                turnText.setAttribute('text-anchor', 'end');
                turnText.setAttribute('font-size', '10px');
                turnText.setAttribute('opacity', '0.8');
                turnText.textContent = node.start_turn + '-' + node.end_turn;
                g.appendChild(turnText);

                // 鼠标事件
                g.addEventListener('mouseenter', (e) => {{
                    if (!isDraggingNode) {{
                        showTooltip(e, node);
                        highlightConnections(node.id);
                    }}
                }});
                g.addEventListener('mousemove', (e) => {{
                    if (!isDraggingNode) moveTooltip(e);
                }});
                g.addEventListener('mouseleave', () => {{
                    if (!isDraggingNode) {{
                        hideTooltip();
                        clearHighlights();
                    }}
                }});

                // 拖拽事件
                g.addEventListener('mousedown', (e) => {{
                    if (e.button === 0) {{ // 左键
                        e.stopPropagation();
                        startDragNode(e, node, g);
                    }}
                }});

                nodesGroup.appendChild(g);
            }});
        }}

        function updateLinkPath(path, source, target) {{
            let d;
            if (isHorizontal) {{
                const sx = source.x + nodeWidth;
                const sy = source.y + nodeHeight / 2;
                const tx = target.x;
                const ty = target.y + nodeHeight / 2;
                const mx = (sx + tx) / 2;
                d = `M${{sx}},${{sy}} C${{mx}},${{sy}} ${{mx}},${{ty}} ${{tx}},${{ty}}`;
            }} else {{
                const sx = source.x + nodeWidth / 2;
                const sy = source.y + nodeHeight;
                const tx = target.x + nodeWidth / 2;
                const ty = target.y;
                const my = (sy + ty) / 2;
                d = `M${{sx}},${{sy}} C${{sx}},${{my}} ${{tx}},${{my}} ${{tx}},${{ty}}`;
            }}
            path.setAttribute('d', d);
        }}

        function updateAllLinks() {{
            const nodeById = {{}};
            allNodes.forEach(n => nodeById[n.id] = n);

            const links = linksGroup.querySelectorAll('.link');
            links.forEach(path => {{
                const sourceId = parseInt(path.getAttribute('data-source'));
                const targetId = parseInt(path.getAttribute('data-target'));
                const source = nodeById[sourceId];
                const target = nodeById[targetId];
                if (source && target) {{
                    updateLinkPath(path, source, target);
                }}
            }});
        }}

        // 节点拖拽
        function startDragNode(e, node, element) {{
            isDraggingNode = true;
            draggedNode = node;
            element.classList.add('dragging');
            hideTooltip();

            const rect = svg.getBoundingClientRect();
            dragStartX = (e.clientX - rect.left - translateX) / scale;
            dragStartY = (e.clientY - rect.top - translateY) / scale;
            nodeStartX = node.x;
            nodeStartY = node.y;

            document.addEventListener('mousemove', onDragNode);
            document.addEventListener('mouseup', stopDragNode);
        }}

        function onDragNode(e) {{
            if (!isDraggingNode || !draggedNode) return;

            const rect = svg.getBoundingClientRect();
            const currentX = (e.clientX - rect.left - translateX) / scale;
            const currentY = (e.clientY - rect.top - translateY) / scale;

            const dx = currentX - dragStartX;
            const dy = currentY - dragStartY;

            draggedNode.x = nodeStartX + dx;
            draggedNode.y = nodeStartY + dy;

            // 更新节点位置
            const nodeElement = document.querySelector(`.node[data-id="${{draggedNode.id}}"]`);
            if (nodeElement) {{
                nodeElement.setAttribute('transform', `translate(${{draggedNode.x}}, ${{draggedNode.y}})`);
            }}

            // 更新连线
            updateAllLinks();
        }}

        function stopDragNode(e) {{
            if (draggedNode) {{
                const nodeElement = document.querySelector(`.node[data-id="${{draggedNode.id}}"]`);
                if (nodeElement) {{
                    nodeElement.classList.remove('dragging');

                    // 如果没有移动太多，触发点击
                    const dx = Math.abs(draggedNode.x - nodeStartX);
                    const dy = Math.abs(draggedNode.y - nodeStartY);
                    if (dx < 5 && dy < 5) {{
                        showModal(draggedNode);
                    }}
                }}
            }}

            isDraggingNode = false;
            draggedNode = null;
            document.removeEventListener('mousemove', onDragNode);
            document.removeEventListener('mouseup', stopDragNode);
        }}

        // 高亮相关连线
        function highlightConnections(nodeId) {{
            // 找出所有相关的连线
            const relatedLinks = new Set();
            const relatedNodes = new Set([nodeId]);

            allLinks.forEach(link => {{
                if (link.source === nodeId || link.target === nodeId) {{
                    relatedLinks.add(`${{link.source}}-${{link.target}}`);
                    relatedNodes.add(link.source);
                    relatedNodes.add(link.target);
                }}
            }});

            // 高亮连线
            const links = linksGroup.querySelectorAll('.link');
            links.forEach(path => {{
                const source = path.getAttribute('data-source');
                const target = path.getAttribute('data-target');
                const key = `${{source}}-${{target}}`;
                if (relatedLinks.has(key)) {{
                    path.classList.add('highlighted');
                    path.classList.remove('dimmed');
                    path.setAttribute('marker-end', 'url(#arrowhead-highlight)');
                }} else {{
                    path.classList.add('dimmed');
                    path.classList.remove('highlighted');
                }}
            }});

            // 高亮节点
            const nodes = nodesGroup.querySelectorAll('.node');
            nodes.forEach(node => {{
                const id = parseInt(node.getAttribute('data-id'));
                if (relatedNodes.has(id)) {{
                    node.classList.add('highlighted');
                    node.classList.remove('dimmed');
                }} else {{
                    node.classList.add('dimmed');
                    node.classList.remove('highlighted');
                }}
            }});
        }}

        function clearHighlights() {{
            const links = linksGroup.querySelectorAll('.link');
            links.forEach(path => {{
                path.classList.remove('highlighted', 'dimmed');
                path.setAttribute('marker-end', 'url(#arrowhead)');
            }});

            const nodes = nodesGroup.querySelectorAll('.node');
            nodes.forEach(node => {{
                node.classList.remove('highlighted', 'dimmed');
            }});
        }}

        function resetPositions() {{
            allNodes.forEach(node => {{
                node.x = node.originalX;
                node.y = node.originalY;
            }});

            // 更新所有节点位置
            const nodes = nodesGroup.querySelectorAll('.node');
            nodes.forEach(nodeEl => {{
                const id = parseInt(nodeEl.getAttribute('data-id'));
                const node = allNodes.find(n => n.id === id);
                if (node) {{
                    nodeEl.setAttribute('transform', `translate(${{node.x}}, ${{node.y}})`);
                }}
            }});

            // 更新连线
            updateAllLinks();
        }}

        function shadeColor(color, percent) {{
            const num = parseInt(color.replace('#', ''), 16);
            const amt = Math.round(2.55 * percent);
            const R = (num >> 16) + amt;
            const G = (num >> 8 & 0x00FF) + amt;
            const B = (num & 0x0000FF) + amt;
            return '#' + (0x1000000 + (R < 255 ? R < 1 ? 0 : R : 255) * 0x10000 +
                (G < 255 ? G < 1 ? 0 : G : 255) * 0x100 +
                (B < 255 ? B < 1 ? 0 : B : 255)).toString(16).slice(1);
        }}

        // 格式化父节点显示
        function formatParentIds(parentIds) {{
            if (!parentIds || parentIds.length === 0) return '无';
            if (parentIds.length === 1 && parentIds[0] === -1) return '无 (根节点)';
            return parentIds.join(', ');
        }}

        // 提示框
        function showTooltip(event, node) {{
            const tooltip = document.getElementById('tooltip');
            const summary = node.summary.length > 150 ? node.summary.substring(0, 150) + '...' : node.summary;
            const parentInfo = formatParentIds(node.parent_ids);
            tooltip.innerHTML = `
                <div class="tooltip-title">
                    <span class="step-num">#${{node.id}}</span>
                    ${{node.title}}
                </div>
                <div class="tooltip-type">${{node.type}} | 轮数: ${{node.start_turn}}-${{node.end_turn}} | 父节点: ${{parentInfo}}</div>
                <div class="tooltip-summary">${{summary || '无摘要'}}</div>
            `;
            tooltip.classList.add('visible');
            moveTooltip(event);
        }}

        function moveTooltip(event) {{
            const tooltip = document.getElementById('tooltip');
            let x = event.clientX + 15;
            let y = event.clientY + 15;

            // 防止超出屏幕
            const rect = tooltip.getBoundingClientRect();
            const maxX = window.innerWidth - 370;
            const maxY = window.innerHeight - rect.height - 20;

            if (x > maxX) x = event.clientX - 360;
            if (y > maxY) y = event.clientY - rect.height - 15;

            tooltip.style.left = x + 'px';
            tooltip.style.top = y + 'px';
        }}

        function hideTooltip() {{
            document.getElementById('tooltip').classList.remove('visible');
        }}

        // 弹窗
        function showModal(node) {{
            document.getElementById('modal-num').textContent = node.id;
            document.getElementById('modal-title').textContent = node.title;
            document.getElementById('modal-type').textContent = node.type;
            document.getElementById('modal-start').textContent = node.start_turn;
            document.getElementById('modal-end').textContent = node.end_turn;
            document.getElementById('modal-parent').textContent = formatParentIds(node.parent_ids);
            document.getElementById('modal-summary').textContent = node.summary || '无摘要';
            document.getElementById('modal-detail').textContent = node.detail || '无详细操作';
            document.getElementById('modal-overlay').classList.add('visible');
        }}

        function closeModal() {{
            document.getElementById('modal-overlay').classList.remove('visible');
        }}

        // 缩放和拖拽
        function initZoomPan() {{
            svg.addEventListener('mousedown', (e) => {{
                if (e.target === svg || e.target.tagName === 'svg') {{
                    isPanning = true;
                    startX = e.clientX - translateX;
                    startY = e.clientY - translateY;
                    svg.style.cursor = 'grabbing';
                }}
            }});

            svg.addEventListener('mousemove', (e) => {{
                if (isPanning) {{
                    translateX = e.clientX - startX;
                    translateY = e.clientY - startY;
                    updateTransform();
                }}
            }});

            svg.addEventListener('mouseup', () => {{
                isPanning = false;
                svg.style.cursor = 'grab';
            }});

            svg.addEventListener('mouseleave', () => {{
                isPanning = false;
                svg.style.cursor = 'grab';
            }});

            svg.addEventListener('wheel', (e) => {{
                e.preventDefault();
                const delta = e.deltaY > 0 ? 0.9 : 1.1;
                const newScale = scale * delta;
                if (newScale >= 0.1 && newScale <= 4) {{
                    // 以鼠标位置为中心缩放
                    const rect = svg.getBoundingClientRect();
                    const mouseX = e.clientX - rect.left;
                    const mouseY = e.clientY - rect.top;

                    translateX = mouseX - (mouseX - translateX) * delta;
                    translateY = mouseY - (mouseY - translateY) * delta;
                    scale = newScale;
                    updateTransform();
                }}
            }});

            // 点击空白处关闭弹窗
            document.getElementById('modal-overlay').addEventListener('click', (e) => {{
                if (e.target.id === 'modal-overlay') {{
                    closeModal();
                }}
            }});

            // ESC关闭弹窗
            document.addEventListener('keydown', (e) => {{
                if (e.key === 'Escape') {{
                    closeModal();
                }}
            }});

            // 点击SVG空白处（非节点）不做特殊处理
            svg.addEventListener('click', (e) => {{
                // 空白处点击不需要做什么
            }});
        }}

        function updateTransform() {{
            mainGroup.setAttribute('transform', `translate(${{translateX}}, ${{translateY}}) scale(${{scale}})`);
        }}

        function zoomIn() {{
            scale *= 1.3;
            if (scale > 4) scale = 4;
            updateTransform();
        }}

        function zoomOut() {{
            scale *= 0.7;
            if (scale < 0.1) scale = 0.1;
            updateTransform();
        }}

        function resetView() {{
            fitToScreen();
        }}

        function fitToScreen() {{
            const bbox = mainGroup.getBBox();
            const container = document.getElementById('graph-container');
            const width = container.clientWidth;
            const height = container.clientHeight;

            if (bbox.width === 0 || bbox.height === 0) {{
                scale = 1;
                translateX = width / 2;
                translateY = height / 2;
            }} else {{
                const padding = 100;
                const scaleX = (width - padding * 2) / bbox.width;
                const scaleY = (height - padding * 2) / bbox.height;
                
                // 对于大型图，使用更小的初始缩放
                let targetScale = Math.min(scaleX, scaleY, 1);
                if (allNodes.length > 100) {{
                    targetScale *= 0.7; // 大图缩小更多
                }} else if (allNodes.length > 50) {{
                    targetScale *= 0.8;
                }} else {{
                    targetScale *= 0.9;
                }}
                
                scale = targetScale;

                // 居中显示，偏向左上角一点（更符合阅读习惯）
                translateX = width * 0.45 - (bbox.x + bbox.width / 2) * scale;
                translateY = height * 0.45 - (bbox.y + bbox.height / 2) * scale;
            }}

            updateTransform();
        }}

        function toggleLayout() {{
            isHorizontal = !isHorizontal;
            customLayerGap = null;
            customNodeGap = null;
            drawGraph();
            setTimeout(fitToScreen, 50);
        }}

        // 间距控制面板
        function toggleSpacingPanel() {{
            const panel = document.getElementById('spacing-panel');
            const btn = document.getElementById('spacing-toggle');
            panel.classList.toggle('visible');
            btn.classList.toggle('active');
        }}

        function updateSpacing() {{
            const layerGap = document.getElementById('layer-gap').value;
            const nodeGap = document.getElementById('node-gap').value;
            document.getElementById('layer-gap-value').textContent = layerGap;
            document.getElementById('node-gap-value').textContent = nodeGap;
        }}

        function applySpacing() {{
            customLayerGap = parseInt(document.getElementById('layer-gap').value);
            customNodeGap = parseInt(document.getElementById('node-gap').value);
            
            // 重新计算位置
            calculatePositions();
            
            // 更新所有节点位置
            const nodes = nodesGroup.querySelectorAll('.node');
            nodes.forEach(nodeEl => {{
                const id = parseInt(nodeEl.getAttribute('data-id'));
                const node = allNodes.find(n => n.id === id);
                if (node) {{
                    nodeEl.setAttribute('transform', `translate(${{node.x}}, ${{node.y}})`);
                }}
            }});
            
            // 更新连线
            updateAllLinks();
            
            // 适应屏幕
            setTimeout(fitToScreen, 50);
        }}

        // 搜索功能
        function searchNodes() {{
            const query = document.getElementById('search-input').value.toLowerCase().trim();
            const resultsContainer = document.getElementById('search-results');
            
            if (!query) {{
                resultsContainer.innerHTML = '';
                clearHighlights();
                return;
            }}
            
            const matches = allNodes.filter(node => {{
                const idMatch = node.id.toString().includes(query);
                const titleMatch = node.title.toLowerCase().includes(query);
                const typeMatch = node.type.toLowerCase().includes(query);
                return idMatch || titleMatch || typeMatch;
            }}).slice(0, 10); // 最多显示10个结果
            
            if (matches.length === 0) {{
                resultsContainer.innerHTML = '<div style="color: #666; font-size: 11px; padding: 5px;">无匹配结果</div>';
                return;
            }}
            
            resultsContainer.innerHTML = matches.map(node => `
                <div class="search-result-item" onclick="focusNode(${{node.id}})">
                    <span class="step-id">#${{node.id}}</span>
                    <span>${{node.title.length > 20 ? node.title.substring(0, 20) + '...' : node.title}}</span>
                </div>
            `).join('');
        }}

        function focusNode(nodeId) {{
            const node = allNodes.find(n => n.id === nodeId);
            if (!node) return;
            
            // 计算居中位置
            const container = document.getElementById('graph-container');
            const width = container.clientWidth;
            const height = container.clientHeight;
            
            // 设置缩放和位置，使节点居中
            scale = 1;
            translateX = width / 2 - (node.x + nodeWidth / 2) * scale;
            translateY = height / 2 - (node.y + nodeHeight / 2) * scale;
            updateTransform();
            
            // 高亮该节点和相关连线
            highlightConnections(nodeId);
            
            // 清空搜索
            document.getElementById('search-input').value = '';
            document.getElementById('search-results').innerHTML = '';
            
            // 3秒后恢复
            setTimeout(clearHighlights, 3000);
        }}

        // 图例
        function generateLegend() {{
            const legend = document.getElementById('legend');
            // 清除旧内容（保留标题）
            const title = legend.querySelector('.legend-title');
            legend.innerHTML = '';
            legend.appendChild(title);

            const typeCounts = {{}};
            allNodes.forEach(n => {{
                typeCounts[n.type] = (typeCounts[n.type] || 0) + 1;
            }});

            const sortedTypes = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);

            sortedTypes.forEach(([type, count]) => {{
                const color = colorMap[type] || colorMap['默认'];
                const item = document.createElement('div');
                item.className = 'legend-item';
                item.innerHTML = `
                    <div class="legend-color" style="background: ${{color}}"></div>
                    <span>${{type}}</span>
                    <span class="legend-count">${{count}}</span>
                `;
                item.addEventListener('click', () => highlightType(type));
                legend.appendChild(item);
            }});
        }}

        function highlightType(type) {{
            const nodes = document.querySelectorAll('.node');
            nodes.forEach(node => {{
                const id = parseInt(node.getAttribute('data-id'));
                const nodeData = allNodes.find(n => n.id === id);
                if (nodeData && nodeData.type === type) {{
                    node.classList.remove('dimmed');
                    node.classList.add('highlighted');
                }} else {{
                    node.classList.remove('highlighted');
                    node.classList.add('dimmed');
                }}
            }});

            // 2秒后恢复
            setTimeout(() => {{
                nodes.forEach(node => {{
                    node.classList.remove('dimmed', 'highlighted');
                }});
            }}, 2000);
        }}

        // 窗口调整
        window.addEventListener('resize', () => {{
            const container = document.getElementById('graph-container');
            svg.setAttribute('width', container.clientWidth);
            svg.setAttribute('height', container.clientHeight);
        }});

        // 启动
        init();
    </script>
</body>
</html>'''

    # 填充模板
    html_content = html_template.format(
        title=title,
        total_steps=graph_data["total_steps"],
        root_count=len(graph_data["root_ids"]),
        link_count=len(graph_data["links"]),
        graph_data_json=json.dumps(graph_data, ensure_ascii=False)
    )

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"HTML可视化文件已生成: {output_file}")


def visualize(
    input_file: str,
    output_file: str = None,
    title: str = "Long-Insight: Trajectory Step Visualization",
) -> str:
    """Generate interactive DAG visualization from step analysis JSON.

    Args:
        input_file: Path to step analysis JSON file.
        output_file: Path for output HTML. Auto-generated if None.
        title: HTML page title.

    Returns:
        Path to the generated HTML file.
    """
    if output_file is None:
        base_name = os.path.splitext(input_file)[0]
        output_file = base_name + '_visualization.html'

    steps = load_steps(input_file)
    print(f"Loaded {len(steps)} steps")

    graph_data = build_graph_data(steps)
    print(f"Root nodes: {len(graph_data['root_ids'])}, Links: {len(graph_data['links'])}")

    generate_html(graph_data, output_file, title)
    return output_file


def main():
    parser = argparse.ArgumentParser(
        description='Generate interactive DAG visualization from step analysis JSON'
    )
    parser.add_argument('input_file', nargs='?',
                        default='steps_analysis.json',
                        help='Input JSON file (default: steps_analysis.json)')
    parser.add_argument('-o', '--output',
                        help='Output HTML file path')
    parser.add_argument('-t', '--title',
                        default='Long-Insight: Trajectory Step Visualization',
                        help='HTML page title')

    args = parser.parse_args()
    visualize(args.input_file, args.output, args.title)


if __name__ == '__main__':
    main()

