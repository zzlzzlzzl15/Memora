#!/usr/bin/env python3
"""
批量修复 documents.py 中所有被 sed 破坏的函数
"""
import re

# 读取文件
with open('/Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/api/documents.py', 'r') as f:
    lines = f.readlines()

# 找到所有包含 "# 单用户模式" 的行
# 在每个这样的行之后，检查下一行是否有文档字符串
# 如果有，在文档字符串之后添加 current_user 定义

fixed_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # 检查是否包含 "# 单用户模式"
    if '# 单用户模式：不再需要用户认证' in line:
        # 保留这一行（作为注释）
        fixed_lines.append(line)
        i += 1
        
        # 检查接下来的行
        j = i
        while j < len(lines) and j < i + 10:  # 最多检查接下来的10行
            next_line = lines[j]
            
            # 如果找到文档字符串（三个引号开头的行）
            if next_line.strip().startswith('"""') or next_line.strip().startswith("'''"):
                fixed_lines.append(next_line)
                j += 1
                
                # 检查下一行是否是函数体开始
                if j < len(lines):
                    body_line = lines[j]
                    # 如果这一行不是注释或空行，则插入 current_user 定义
                    if body_line.strip() and not body_line.strip().startswith('#'):
                        # 在这里插入 current_user 定义
                        indent = '    '  # 4个空格缩进
                        fixed_lines.append(f'{indent}current_user = {{"user_id": 1, "sub": "admin"}}\n')
                        i = j
                        break
            
            # 如果找到其他内容（非文档字符串的行）
            if not (next_line.strip().startswith('"""') or next_line.strip().startswith("'''")):
                # 如果下一行没有文档字符串，直接在注释后插入 current_user
                if j == i:  # 还没有处理文档字符串
                    indent = '    '
                    fixed_lines.append(f'{indent}current_user = {{"user_id": 1, "sub": "admin"}}\n')
                    i = j
                    break
            j += 1
        
        if j >= i + 10:
            # 达到最大检查范围，继续处理
            i = j
    else:
        fixed_lines.append(line)
        i += 1

# 写入文件
with open('/Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/api/documents.py', 'w') as f:
    f.writelines(fixed_lines)

print("documents.py 批量修复完成")
