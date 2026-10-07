# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BhookOuyang <https://github.com/BhookOuyang>

"""Translation dictionary for Aurora's Node Manager."""

import bpy


def tr(msgid):
    """Translate a message template; returns the English source when unavailable.

    Use this only for dynamic/format strings (e.g. ``tr("Shard {}/{}").format(n, m)``).
    Static UI strings (labels, operator buttons, property names) are translated
    automatically by Blender via ``translations_dict``.
    """
    try:
        return bpy.app.translations.pgettext(msgid)
    except Exception:
        return msgid


translations_dict = {
    "zh_CN": { 
        # Generic UI context ("*"): panels, labels, properties, enum items,
        # report messages and dynamic message templates.


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
        ("*", "Unknown Patterns"): "未知模式",
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

        # AddonPreferences properties (bpy.props use the "*" context)
        ("*", "Use Custom Storage Path"): "使用自定义存储路径",
        ("*", "Patterns Storage Path"): "模式存储路径",
        ("*", "Auto-migrate on path change"): "更改路径时自动迁移",
        ("*", "Show Advanced Options"): "显示高级选项",
        ("*", "Store Absolute File Paths"): "存储绝对文件路径",
        ("*", "Auto-delete Risky File Types"): "自动删除风险文件类型",
        ("*", "Log Storage Path"): "日志存储路径",
        ("*", "Logging"): "日志",
        ("*", "General"): "常规",
        ("*", "Export Logs"): "导出日志",
        ("*", "Clear Logs"): "清除日志",
        ("*", "Report Issue"): "报告问题",
        ("*", "Enable Sharded Transfer"): "启用分片传输",
        ("*", "Shard Size"): "分片大小",
        ("*", "Enable Data Encryption"): "启用数据加密",
        ("*", "Encryption Password"): "加密密码",
        ("*", "Decrypt Password"): "解密密码",
        ("*", "Category"): "分类",
        ("*", "Pattern Name"): "模式名称",
        ("*", "Name"): "名称",
        ("*", "Description"): "描述",
        ("*", "Author"): "作者",
        ("*", "Created"): "创建时间",
        ("*", "Version"): "版本",
        ("*", "Ignore Version Mismatch"): "忽略版本差异",

        ("*", "Enable to use a custom directory for storing node patterns"): "启用后使用自定义目录来存储节点模式",
        ("*", "Custom directory for storing node patterns"): "用于存储节点模式的自定义目录",
        ("*", "Automatically move pattern files to the new path when changed"): "更改路径时自动将模式文件移动到新路径",
        ("*", "Show advanced serialization options"): "显示高级序列化选项",
        ("*", "Save the absolute file paths of referenced files (images, clips, scripts, IES, etc.) so they can be reloaded locally. Paths are stripped when copying to clipboard or exporting .aurpak for sharing."): "保存引用文件（图片、影片剪辑、脚本、IES 等）的绝对路径以便本地重新加载；复制到剪贴板或导出 .aurpak 分享时会剔除这些路径",
        ("*", "Automatically delete blacklisted/risky file types when importing resource packs; when disabled, these files are shown in a dialog for manual decision."): "导入资源包时自动删除黑名单等风险文件类型；关闭后此类文件会进入弹窗由你手动决定",
        ("*", "Show logging options"): "显示日志选项",
        ("*", "Directory where session log files are stored; leave empty to use the default user scripts folder."): "会话日志文件的存放目录；留空则使用默认的用户脚本目录",
        ("*", "Select the log files to export into a single archive file"): "选择要合并导出到一个文件的日志条目",
        ("*", "Delete all stored log files"): "删除所有已保存的日志文件",
        ("*", "No log files found"): "没有找到日志文件",
        ("*", "entries"): "条记录",
        ("*", "No logs selected"): "未选择日志",
        ("*", "Export failed"): "导出失败",
        ("*", "Exported {} logs to {}"): "已导出 {} 个日志到 {}",
        ("*", "No log files to clear"): "没有可清除的日志文件",
        ("*", "Cleared {} log file(s)"): "已清除 {} 个日志文件",
        ("*", "{} log file(s) · {}"): "{} 个日志文件 · {}",
        ("*", "Internal error, details written to the log file"): "发生内部错误，详情已写入日志文件",
        ("*", "Split clipboard data into multiple shards of a fixed size, sent one at a time; the receiver reassembles and decodes them automatically once all are collected."): "将复制到剪贴板的数据按指定大小切成多个分片，逐片发送；接收方收集齐后自动拼接解码",
        ("*", "Maximum number of characters per shard."): "每个分片数据段的最大字符数",
        ("*", "Encrypt clipboard data with a password; the receiver must enter the correct password to decode it."): "用密码对剪贴板数据进行加密；接收方必须输入正确的密码才能解码",
        ("*", "Password used for encryption (the receiver must enter the same password to decode). Leave empty to be prompted before copying."): "加密所用密码（接收方需输入相同密码才能解码）。留空时复制前会弹出输入框",

        # Shard size preset enum items
        ("*", "500 chars"): "500 字符",
        ("*", "1000 chars"): "1000 字符",
        ("*", "2000 chars"): "2000 字符",
        ("*", "4000 chars"): "4000 字符",
        ("*", "8000 chars"): "8000 字符",
        ("*", "Up to 500 chars per shard, for very restrictive channels."): "每片最多 500 字符，适合限制极严的渠道",
        ("*", "Up to 1000 chars per shard."): "每片最多 1000 字符",
        ("*", "Up to 2000 chars per shard (default)."): "每片最多 2000 字符（默认）",
        ("*", "Up to 4000 chars per shard, for long-message channels."): "每片最多 4000 字符，适合长消息渠道",
        ("*", "Up to 8000 chars per shard."): "每片最多 8000 字符",

        # AddonPreferences misc
        ("*", "You found the easter egg!"): "你发现了彩蛋！",

        # Panel & Operator buttons (labels drawn directly, e.g. layout.label)
        ("*", "Export"): "导出",
        ("*", "Import"): "导入",
        ("*", "Paste"): "粘贴",
        ("*", "Copy"): "复制",
        ("*", "Send Shards"): "分片发送",
        ("*", "Receive Shards"): "分片接收",
        ("*", "Copied"): "已复制",
        ("*", "Not copied"): "未复制",
        ("*", "All shards received, processing…"): "分片已全部接收，正在处理…",
        ("*", "This batch is encrypted"): "该批数据已加密",
        ("*", "Clipboard transfer options"): "剪贴板传输选项",
        ("*", "Only Modified"): "仅修改项",
        ("*", "Exclude defaults to reduce size. Defaults depend on current Blender version."): "剔除节点默认值以得到更小的数据体积。注意：默认值可能随Blender版本变化，加载效果以当前版本为准",
        ("*", "✨ Experimental Features"): "✨ 实验功能",

        # Dynamic message templates (format with .format() after tr())
        ("*", "Shard Transfer · Copied {}/{}"): "分片传输  ·  已复制 {}/{}",
        ("*", "Shard {}/{}"): "第 {}/{} 片",
        ("*", "Received {}/{}"): "已接收 {}/{}",
        ("*", "Too many shards, showing first {}"): "分片较多，只展示前 {} 个",
        ("*", "All shards received ({}), enter password to decrypt"): "分片已收齐（{} 片），请输入密码解密",

        # Version warning draws
        ("*", "Major version difference may cause unexpected errors"): "主版本差异可能导致不可预知的错误",
        ("*", "Cancelled: Blender major version mismatch"): "已取消：Blender 主版本不匹配",
        ("*", "No placeholder reroutes will be created"): "跳过不支持节点时不会生成占位转节点",
        ("*", "Cross-Platform Warning"): "跨平台警告",
        ("*", "Node group created on {platform}. Cross-platform loading may result in subtle differences in rendering and computation."): "节点组创建于 {platform}。跨平台加载时，渲染与计算效果可能存在细微差异。",

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

        # Load operator properties (bpy.props, "*" context)
        ("*", "Target Type"): "目标类型",
        ("*", "Auto"): "自动",
        ("*", "Create Placeholders"): "生成占位符",
        ("*", "Remove Orphan Islands"): "删除孤岛",
        ("*", "Trim"): "修剪",

        ("*", "Force load into different node tree type"): "强制加载到不同的节点树类型",
        ("*", "Create [MISSING] reroute placeholders for unsupported nodes"): "为不支持的节点创建 [MISSING] 占位转节点",
        ("*", "Remove orphan nodes, empty frames, and reroute-only chains"): "移除孤立节点、空框架和纯转节点链",
        ("*", "Trim dangling reroute chains that connect to a real node on only one side"): "修剪一端连真实节点、另一端悬空的转节点链",

        ("*", "Use pattern's original type"): "使用模式的原始类型",
        ("*", "Load as shader nodes"): "作为着色器节点加载",
        ("*", "Load as compositor nodes"): "作为合成器节点加载",
        ("*", "Load as geometry nodes"): "作为几何节点加载",

        # Pattern info properties (bpy.props, "*" context)
        ("*", "Node Count"): "节点数",
        ("*", "Group Count"): "组数",
        ("*", "Node Type"): "节点类型",
        ("*", "Format Version"): "格式版本",
        ("*", "File Name"): "文件名",
        ("*", "Locked"): "已锁定",
        ("*", "Has Groups"): "包含组",
        ("*", "Tags"): "标签",

        # Overwrite confirmation
        ("*", "Confirm overwrite?"): "确定覆盖吗？",
        ("*", "Confirm overwrite to Shader type?"): "确认重写为着色器类型节点吗？",
        ("*", "Confirm overwrite to Compositor type?"): "确认重写为合成器类型节点吗？",
        ("*", "Confirm overwrite to Geometry type?"): "确认重写为几何节点类型节点吗？",

        # Resource pack dialogs
        ("*", "Pack Resources"): "打包资源",
        ("*", "Validate and pack resource files referenced by nodes (images/IES/videos/audio, etc.) into the pack; absolute paths never leak, the receiver may choose whether to keep them."): "将节点引用的资源文件（图片/IES/视频/音频等）校验后打包进压缩包；绝对路径绝不外泄，接收方可选择是否保留",
        ("*", "Keep Resource Pack"): "保留资源包",
        ("*", "Keep these resources (keep-all)"): "保留这些资源（保留则全部保留）",
        ("*", "Storage Location"): "存储位置",
        ("*", "This pack includes a resource pack:"): "此压缩包附带了资源包：",
        ("*", "{} resource files, {:.2f} MB total"): "{} 个资源文件，共 {:.2f} MB",
        ("*", "Resource pack exceeds size limit: {}"): "资源包超出大小限制: {}",
        ("*", "The pack contains foreign files that will be treated as tampering and deleted"): "压缩包含外来文件，将被视为非法篡改删除",
        ("*", "Not keeping will discard the resources without checks"): "不保留将直接丢弃资源（不做检查）",
        ("*", "The resource pack contains unexpected extra resource types:"): "资源包包含意外的附加资源类型：",
        ("*", "Not keeping will delete all of them (default)."): "不保留则全部删除（默认）。",
        ("*", "Choose where to store the resource files:"): "选择资源文件的存储位置：",
        ("*", "Enter the password to decrypt node data"): "输入密码以解密节点数据",
        ("*", "Enter the password to decrypt encrypted node data in the clipboard"): "输入密码解密剪贴板中的加密节点数据",
        ("*", "Encryption password used for this copy."): "本次复制使用的加密密码",
        ("*", "Export the selected pattern as an .aurpak file"): "将选中的模式导出为 .aurpak 文件",
        ("*", "Import patterns from an .aurpak or .zip file"): "从 .aurpak 或 .zip 文件导入模式",
        ("*", "Copy the selected pattern to clipboard as a bundle JSON"): "将选中的模式作为打包 JSON 复制到剪贴板",
        ("*", "Import a pattern from clipboard"): "从剪贴板导入模式",
        ("*", "Shader node patterns"): "着色器节点模式",
        ("*", "Compositor node patterns"): "合成器节点模式",
        ("*", "Geometry node patterns"): "几何节点模式",
        ("*", "Nothing to undo yet"): "暂无可以撤销的操作",

        # Operator tooltips (bl_description, "*" context)
        ("*", "Save the selected node state as a pattern file"): "将选中的节点状态保存为模式文件",
        ("*", "Load the selected pattern into the node editor"): "将选中的模式加载到节点编辑器中",
        ("*", "Delete the selected pattern"): "删除选中的模式",
        ("*", "Edit the metadata of the selected pattern"): "编辑选中模式的元数据",
        ("*", "Overwrite the selected pattern with the current node state"): "用当前节点状态覆盖选中的模式",
        ("*", "Toggle the lock of the selected pattern"): "切换选中模式的锁定状态",
        ("*", "Restore the selected cached pattern"): "恢复选中的缓存模式",
        ("*", "Undo the last overwrite/delete operation"): "撤销上一步覆盖或删除操作",
        ("*", "Move pattern files to the new storage path"): "将模式文件移动到新的存储路径",
        ("*", "Copy a single shard to the clipboard"): "复制单个分片到剪贴板",
        ("*", "Clear the current shard send session"): "清空当前分片发送会话",
        ("*", "Clear the current shard receive session"): "清空当前分片接收会话",
        ("*", "Inspect the RNA properties of the selected node"): "查看选中节点的 RNA 属性",
        ("*", "Paste the next shard from the clipboard"): "从剪贴板粘贴下一个分片",

        # Pattern list active index (node_pattern_active_index)
        ("*", "Active Index"): "活动索引",

        # Pattern list item properties (NodePatternItem, "*" context)
        ("*", "Name of the pattern as shown in the list"): "列表中显示的模式名称",
        ("*", "Relative path of the pattern file in the storage directory"): "模式文件在存储目录中的相对路径",
        ("*", "Whether the pattern is locked against overwriting"): "该模式是否已锁定禁止覆盖",
        ("*", "Number of nodes in the pattern"): "模式中的节点数量",
        ("*", "Whether the pattern contains node groups"): "该模式是否包含节点组",
        ("*", "Type of the node tree the pattern was saved from"): "该模式来源的节点树类型",

        # Report messages (static)
        ("*", "No pattern selected"): "未选中模式",
        ("*", "Pattern file not found"): "未找到模式文件",
        ("*", "Failed to import pattern"): "模式导入失败",
        ("*", "Clipboard is empty"): "剪贴板为空",
        ("*", "No pending import data"): "没有待导入的数据",
        ("*", "Please choose a resource storage location"): "请选择资源存储位置",
        ("*", "No shard session"): "没有分片会话",
        ("*", "Invalid shard number"): "分片序号无效",
        ("*", "Send session cleared"): "发送会话已清空",
        ("*", "Receive session cleared"): "接收会话已清空",
        ("*", "Incomplete shard info"): "分片信息不完整",
        ("*", "No active shard session"): "没有进行中的分片会话",
        ("*", "Clipboard is empty; copy a shard first"): "剪贴板为空，请先复制一个分片",
        ("*", "Clipboard content is not a shard"): "剪贴板内容不是分片",
        ("*", "Shard from a different batch, ignored"): "分片来自不同批次，已忽略",
        ("*", "No pending encrypted data"): "没有待解密的数据",
        ("*", "Please enter the decrypt password"): "请输入解密密码",
        ("*", "No encryption password set"): "未设置加密密码",
        ("*", "JSON contains resource tokens but the pack has no resource pack; cannot resolve references"): "JSON 含资源令牌但压缩包中无资源包，无法解析引用",

        # Report messages (dynamic templates)
        ("*", "JSON contains non-token paths that cannot be matched to resources ({} issue(s)): {}"): "JSON 含非令牌路径，无法对应资源（{} 处）：{}",
        ("*", "Foreign file (tamper evidence) ignored: {}"): "外来文件（非法篡改）已忽略: {}",
        ("*", "Discarded resource pack, imported pattern: {}"): "已丢弃资源包，导入模式: {}",
        ("*", "Tampered/risky file deleted: {}"): "非法篡改/风险文件已删除: {}",
        ("*", "Imported pattern: {} ({} resource(s) extracted)"): "Imported pattern: {}（已解压 {} 个资源）",
        ("*", ", {} integrity-flagged file(s) deleted"): "，{} 个内容异常已删除",
        ("*", "Shard 1/{} copied; keep copying shards from the transfer window"): "分片 1/{} 已复制，传输窗口可继续逐片复制",
        ("*", "Copied shard {}/{}"): "已复制第 {}/{} 片",
        ("*", "All shards received; enter the password in the transfer window to decrypt"): "分片已收齐，请在传输窗口输入密码解密",
        ("*", "Exported to {}"): "已导出到 {}",
        ("*", "Imported pattern: {}"): "已导入模式：{}",
        ("*", "Pasted pattern: {}"): "已粘贴模式：{}",
        ("*", "Copied to clipboard: {}"): "已复制到剪贴板：{}",
        ("*", "Migrated {} pattern files"): "已迁移 {} 个模式文件",

        # core.transport messages
        ("*", "Password cannot be empty"): "密码不能为空",
        ("*", "Encrypted data format is invalid"): "加密数据格式不正确",
        ("*", "Incorrect password; cannot decrypt"): "密码错误，无法解密",
        ("*", "Shard size must be greater than 0"): "分片大小必须大于 0",
        ("*", "No shards to assemble"): "没有可拼接的分片",
        ("*", "Missing shard metadata"): "分片元数据缺失",
        ("*", "Invalid shard number: {}"): "分片序号无效: {}",
        ("*", "Incomplete shards, missing: {}"): "分片不完整，缺少: {}",
        ("*", "Shard data length mismatch (expected {}, got {})"): "分片数据长度不符（期望 {}，实际 {}）",
        ("*", "Shard data verification failed (possibly corrupted in transit)"): "分片数据校验失败（可能传输中损坏）",
        ("*", "Inconsistent shard total"): "分片总数不一致",
        ("*", "Shard from a different batch, ignored (current batch {}…)"): "分片来自不同批次，已忽略（当前批次 {}…）",
        ("*", "Shard {}/{} already received, skipped"): "第 {}/{} 片已接收，跳过",
        ("*", "Received shard {}/{}"): "已接收第 {}/{} 片",

        # utils.file_utils messages
        ("*", "Referenced file missing, removed: {}"): "引用文件不存在，已剔除: {}",
        ("*", "{} (unknown type)"): "{}（未知类型）",
        ("*", "Unsupported file type, removed: {}"): "不支持文件类型，已剔除: {}",
        ("*", "Failed to read referenced file, removed: {}"): "读取引用文件失败，已剔除: {}",
        ("*", "Referenced file structure anomaly, removed: {}"): "引用文件结构异常，已剔除: {}",
        ("*", "{} too large"): "{} 过大",
        ("*", "Too many entries ({})"): "条目数超限 ({})",
        ("*", "Entry decompressed size exceeds limit: {}"): "单条解压大小超限: {}",
        ("*", "Total decompressed size exceeds limit"): "解压总量超限",
        ("*", "Failed to read resource pack: {}"): "资源包读取失败: {}",
        ("*", "{} decompressed size exceeds limit"): "{} 解压大小超限",
        ("*", "{} verification failed"): "{} 校验失败",
        ("*", "Cannot create directory: {} ({})"): "无法创建目录: {} ({})",
        ("*", "Abnormal resource path, not extracted: {}"): "资源路径异常，未解压: {}",
        ("*", "Content integrity anomaly (not in manifest), deleted: {}"): "内容完整性异常（不在清单内），已删除: {}",
        ("*", "Failed to read resource, deleted: {}"): "资源读取失败，已删除: {}",
        ("*", "Risky file type"): "风险文件类型",
        ("*", "Unexpected resource type"): "意外的资源类型",
        ("*", "{}, deleted: {}"): "{}，已删除: {}",
        ("*", "Content integrity anomaly (possibly tampered), deleted: {}"): "内容完整性异常（可能被篡改），已删除: {}",

        # Bug report
        ("*", "Have a bug? Tell me:"): "遇到 bug？告诉我：",
        ("*", "Contact Me"): "联系我",
        ("*", "GitHub Issues (with Blender version & node info)"): "GitHub Issues（备注 Blender 版本号和节点信息）",
        ("*", "Bilibili: 欧阳魄鬼"): "Bilibili: 欧阳魄鬼",
        ("*", "Twitter / X: @BhookOuyang"): "Twitter / X：@BhookOuyang",


        # Operator context ("Operator"): operator bl_labels and operator
        # button text (layout.operator(text=...)).

        ("Operator", "Save Selected"): "保存选中节点",
        ("Operator", "Load"): "加载",
        ("Operator", "Overwrite"): "覆盖",
        ("Operator", "Delete"): "删除",
        ("Operator", "Edit"): "编辑",
        ("Operator", "Lock"): "锁定",
        ("Operator", "Unlock"): "解锁",
        ("Operator", "Export"): "导出",
        ("Operator", "Import"): "导入",
        ("Operator", "Paste"): "粘贴",
        ("Operator", "Copy"): "复制",
        ("Operator", "Save Node Pattern"): "保存节点模式",
        ("Operator", "Edit Pattern Info"): "编辑模式信息",
        ("Operator", "Copy Pattern"): "复制模式",
        ("Operator", "Paste Pattern"): "粘贴模式",
        ("Operator", "Export Pattern"): "导出模式",
        ("Operator", "Import Pattern"): "导入模式",
        ("Operator", "Delete Pattern"): "删除模式",
        ("Operator", "Load Pattern"): "加载模式",
        ("Operator", "Overwrite Pattern"): "覆盖模式",
        ("Operator", "Restore Pattern"): "恢复模式",
        ("Operator", "Undo Last"): "撤销上一步",
        ("Operator", "Toggle Lock Pattern"): "切换锁定模式",
        ("Operator", "Restore"): "恢复",
        ("Operator", "Migrate Patterns"): "迁移模式",
        ("Operator", "RNA Inspector"): "RNA 查看器",
        ("Operator", "Keep Resource Pack?"): "是否保留资源包",
        ("Operator", "Unexpected Extra Resource Types"): "意外的附加资源类型",
        ("Operator", "Choose Resource Storage Location"): "选择资源存储位置",
        ("Operator", "Copy Shard"): "复制分片",
        ("Operator", "Clear Shard Session"): "清空分片会话",
        ("Operator", "Clear Receive Session"): "清空接收会话",
        ("Operator", "Paste Next Shard"): "粘贴下一分片",
        ("Operator", "Enter Password to Decrypt"): "输入密码解密",
        ("Operator", "Clear Session"): "清空会话",
        ("Operator", "Decrypt & Paste"): "解密并粘贴",
        ("Operator", "🔍 Inspect Selected Node RNA"): "🔍 检查选中节点的 RNA",
    }
}
