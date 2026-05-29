"""Translation dictionary for Aurora's Node Manager."""

translations_dict = {
    "zh_CN": {
        # UI Labels
        ("*", "Save Selected"): "保存选中节点",
        ("*", "Load"): "加载",
        ("*", "Overwrite"): "覆盖",
        ("*", "Delete"): "删除",
        ("*", "Edit"): "编辑",
        ("*", "Lock"): "锁定",
        ("*", "Unlock"): "解锁",
        ("*", "Pattern Info"): "模式信息",
        ("*", "Node Patterns"): "节点模式",
        ("*", "Shader"): "着色器",
        ("*", "Compositor"): "合成器",
        ("*", "Geometry"): "几何节点",
        ("*", "Shader Patterns"): "着色器节点模式",
        ("*", "Compositor Patterns"): "合成器节点模式",
        ("*", "Geometry Patterns"): "几何节点模式",
        ("*", "No patterns in this category"): "该分类下没有模式",
        ("*", "Unknown"): "未知",
        ("*", "Author's Note:"): "作者说明：",

        # Info panel
        ("*", "Type:"): "类型：",
        ("*", "Description:"): "描述：",
        ("*", "Author:"): "作者：",
        ("*", "Created:"): "创建时间：",
        ("*", "Version:"): "版本：",
        ("*", "Format:"): "格式：",
        ("*", "Nodes:"): "节点数：",
        ("*", "Groups:"): "组数：",

        # AddonPreferences
        ("rna_label", "Use Custom Storage Path"): "使用自定义存储路径",
        ("rna_label", "Patterns Storage Path"): "模式存储路径",
        ("rna_label", "Auto-migrate on path change"): "更改路径时自动迁移",
        ("rna_label", "Show Advanced Options"): "显示高级选项",
        ("rna_label", "Category"): "分类",
        ("rna_label", "Pattern Name"): "模式名称",
        ("rna_label", "Name"): "名称",
        ("rna_label", "Description"): "描述",
        ("rna_label", "Author"): "作者",
        ("rna_label", "Created"): "创建时间",
        ("rna_label", "Version"): "版本",
        ("rna_label", "Ignore Version Mismatch"): "忽略版本差异",

        ("rna_description", "Enable to use a custom directory for storing node patterns"): "启用后使用自定义目录来存储节点模式",
        ("rna_description", "Custom directory for storing node patterns"): "用于存储节点模式的自定义目录",
        ("rna_description", "Automatically move pattern files to the new path when changed"): "更改路径时自动将模式文件移动到新路径",
        ("rna_description", "Show advanced serialization options"): "显示高级序列化选项",
        ("rna_description", "Shader node patterns"): "着色器节点模式",
        ("rna_description", "Compositor node patterns"): "合成器节点模式",
        ("rna_description", "Geometry node patterns"): "几何节点模式",
        ("rna_description", "Load even if Blender major version differs from saved pattern"): "即使保存版本与当前 Blender 主版本不同也继续加载",
        ("rna_description", "Overwrite even if Blender major version differs"): "即使保存版本与当前 Blender 主版本不同也继续覆盖",

        # Panel & Operator buttons
        ("*", "Export"): "导出",
        ("*", "Import"): "导入",
        ("*", "Paste"): "粘贴",
        ("*", "Copy"): "复制",
        ("*", "Save Node Pattern"): "保存节点模式",
        ("*", "Edit Pattern Info"): "编辑模式信息",
        ("*", "Copy Pattern"): "复制模式",
        ("*", "Paste Pattern"): "粘贴模式",
        ("*", "Export Pattern"): "导出模式",
        ("*", "Import Pattern"): "导入模式",
        ("*", "Delete Pattern"): "删除模式",
        ("*", "Load Pattern"): "加载模式",
        ("*", "Overwrite Pattern"): "覆盖模式",
        ("*", "Restore Pattern"): "恢复模式",
        ("*", "Undo Last"): "撤销上一步",
        ("*", "Toggle Lock Pattern"): "切换锁定模式",
        ("*", "Nothing to undo yet"): "还没有可撤回的操作呢",
        ("*", "Recovery"): "恢复",
        ("*", "Migrate Patterns"): "迁移模式",
        ("*", "Advanced"): "高级",

        # Version warning draws
        ("*", "Major version difference may cause unexpected errors"): "主版本差异可能导致不可预知的错误",
        ("*", "Cancelled: Blender major version mismatch"): "已取消：Blender 主版本不匹配",
        ("*", "No placeholder reroutes will be created"): "跳过不支持节点时不会生成占位转节点",

        # RNA Inspector
        ("*", "RNA Inspector"): "RNA 查看器",
        ("*", "RNA Properties"): "RNA 属性",
        ("*", "Inputs"): "输入",
        ("*", "Outputs"): "输出",
        ("*", "(none)"): "（无）",
        ("*", "No active node"): "未选中节点",
        ("*", "No serializable properties found"): "未发现可序列化的属性",

        # Advanced panel
        ("*", "Nothing here yet"): "这里还什么都没有呢",
        ("*", "check back next version~ (◕‿◕✿)"): "下个版本再来看看吧~ (◕‿◕✿)",

        # Load operator properties
        ("rna_label", "Target Type"): "目标类型",
        ("rna_label", "Auto"): "自动",
        ("rna_label", "Create Placeholders"): "生成占位符",
        ("rna_label", "Remove Orphan Islands"): "删除孤岛",
        ("rna_label", "Trim"): "修剪",

        ("rna_description", "Force load into different node tree type"): "强制加载到不同的节点树类型",
        ("rna_description", "Create [MISSING] reroute placeholders for unsupported nodes"): "为不支持的节点创建 [MISSING] 占位转节点",
        ("rna_description", "Remove orphan nodes, empty frames, and reroute-only chains"): "移除孤立节点、空框架和纯转节点链",
        ("rna_description", "Trim dangling reroute chains that connect to a real node on only one side"): "修剪一端连真实节点、另一端悬空的转节点链",

        ("*", "Auto"): "自动",
        ("*", "Use pattern's original type"): "使用模式的原始类型",
        ("*", "Load as shader nodes"): "作为着色器节点加载",
        ("*", "Load as compositor nodes"): "作为合成器节点加载",
        ("*", "Load as geometry nodes"): "作为几何节点加载",

        # Pattern info properties
        ("rna_label", "Node Count"): "节点数",
        ("rna_label", "Group Count"): "组数",
        ("rna_label", "Node Type"): "节点类型",
        ("rna_label", "Format Version"): "格式版本",
        ("rna_label", "File Name"): "文件名",
        ("rna_label", "Locked"): "已锁定",
        ("rna_label", "Has Groups"): "包含组",
        ("rna_label", "Tags"): "标签",

        # Overwrite confirmation
        ("*", "Confirm overwrite?"): "确定覆盖吗？",
        ("*", "Confirm overwrite to Shader type?"): "确认重写为着色器类型节点吗？",
        ("*", "Confirm overwrite to Compositor type?"): "确认重写为合成器类型节点吗？",
        ("*", "Confirm overwrite to Geometry type?"): "确认重写为几何节点类型节点吗？",

        # Bug report
        ("*", "If you run into any issues, please let me know:"): "如果你遇到了任何问题，请告诉我：",
        ("*", "GitHub Issues (with Blender version & node info)"): "GitHub Issues（备注 Blender 版本号和节点信息）",
        ("*", "Bilibili: 欧阳魄鬼"): "Bilibili: 欧阳魄鬼",
        ("*", "Twitter / X: @BhookOuyang"): "Twitter / X：@BhookOuyang",
    }
}
