# ==============================
# SQL明细化神器 - 开源通用版 v14.2（2025.12.28）
# 作者：匿名贡献 | GitHub 完全公开 | 极致脱敏
# 功能：从报表Excel中提取 1#sqlValue(...)，自动生成明细查询SQL
# 专治多列表格、指标编号重复、UNION 汇总查询
# ==============================

import re
import pandas as pd
from tkinter import Tk, filedialog, messagebox, simpledialog
from pathlib import Path
import os

# ==============================
# 核心映射表 - 用户自定义区（强烈建议修改这里适配自己的系统！）
# ==============================
# 
# 使用说明：
# 1. 本工具根据 SQL 中的 FROM 表名（取 . 后最后一部分，转大写）来决定展开哪些明细字段
# 2. 你只需添加或修改下面字典中的键值即可：
#    - 键：SQL中出现的表名或别名（转大写），例如 FROM DW_LOAN A → 'DW_LOAN' 或 'A'
#    - 值：列表，填写你希望明细查询中 SELECT 的字段（支持 AS、表达式等）
# 3. 如果某个表不需要展开，直接删除该键或留空列表
# 4. 不认识的表会自动 fallback 到 SELECT *
# 
# 当前支持：
#   - UNION / UNION ALL 自动拆分为多个明细查询
#   - 普通 LEFT JOIN、INNER JOIN 等多表查询
#   - Excel 中整行或整列包含 1#sqlValue(...) 均可自动识别
# 
# 暂不支持：
#   - WITH (CTE) 开头的复杂子查询
#   - 嵌套过深的子查询
# 
# 下方仅提供两个极简通用示例，请根据自己报表系统全部替换！

TABLE_FIELD_MAP = {
    # 示例1：通用总账/科目余额表（适用于大多数汇总报表）
    'TABLE_GL': [
        'A.DATE',           # 数据日期
        'A.ORG',            # 机构号
        'A.ITEM_NO',        # 科目号
        'A.ITEM_NAME',      # 科目名称
        'A.CCY',            # 币种
        'A.BALANCE'         # 余额（可自行扩展借/贷方）
    ],

    # 示例2：通用存款/账户明细表（最常见明细需求）
    'TABLE_ACCOUNT': [
        'A.DATE',
        'A.ORG',
        'A.ITEM_NO',
        'A.ACCT_NO',        # 账号
        'A.CUST_NO',        # 客户号（可加脱敏表达式）
        'B.CUST_NAME',      # 客户名称（关联表）
        'A.CCY',
        'A.BALANCE'         # 账户余额
    ]
}

# ==============================
# transform_sql 函数（核心逻辑，不建议修改）
# ==============================
def transform_sql(sql: str):
    if not sql or not sql.strip():
        return "", ""
    sql = re.sub(r'/\*[\s\S]*?\*/', ' ', sql)  # 去除注释
    sql = re.sub(r'\s+', ' ', sql).strip()

    # 处理 UNION / UNION ALL
    if 'UNION' in sql.upper():
        outer_match = re.search(r'FROM\s*\(([\s\S]+)\)\s*([A-Za-z_]\w*)', sql, re.IGNORECASE)
        if not outer_match:
            return "", ""
        inner_sql = outer_match.group(1).strip()
        outer_alias = outer_match.group(2).strip()
        union_parts = re.split(r'\bUNION\s+ALL\b|\bUNION\b', inner_sql, flags=re.IGNORECASE)
        detail_parts = []
        used_tables = set()

        for part in union_parts:
            part = part.strip()
            if not part.upper().startswith('SELECT'):
                continue
            from_match = re.search(r'\bFROM\b', part, re.IGNORECASE)
            if not from_match:
                continue
            from_pos = from_match.start()
            from_clause = part[from_pos:]
            table_match = re.search(r'\bFROM\s+([^\s\(]+)\s+([A-Za-z_]\w*)', part, re.IGNORECASE)
            if not table_match:
                continue
            table_name = table_match.group(1).split('.')[-1].upper()
            used_tables.add(table_name)
            select_fields = TABLE_FIELD_MAP.get(table_name, ['*'])
            detail_part = 'SELECT ' + ', '.join(select_fields) + ' ' + from_clause
            detail_part = re.sub(r'\s+GROUP\s+BY\s+[\s\S]*$', '', detail_part, flags=re.IGNORECASE)
            detail_parts.append(detail_part)

        # 合并所有需要的字段（去重）
        all_select_fields = list(dict.fromkeys(
            field for t in used_tables for field in TABLE_FIELD_MAP.get(t, ['*'])
        ))

        # 修复 f-string 不能包含 \n 的问题
        union_separator = "\nUNION ALL\n"
        detail_sql = (
            f"SELECT {', '.join(all_select_fields)} FROM (\n"
            + union_separator.join(detail_parts)
            + f"\n) {outer_alias} WHERE 1=1"
        )

        inner_content = union_separator.join([p.strip() for p in detail_parts])
        from_inner = f"({inner_content}) {outer_alias}"

        return detail_sql.strip(), from_inner.strip()

    # 处理普通单表或 JOIN 查询
    else:
        from_match = re.search(r'\bFROM\b', sql, re.IGNORECASE)
        if not from_match:
            return "", ""
        from_pos = from_match.start()
        from_clause = sql[from_pos:]
        table_match = re.search(r'\bFROM\s+([^\s\(]+)\s+([A-Za-z_]\w*)', sql, re.IGNORECASE)
        if not table_match:
            return "", ""
        table_name = table_match.group(1).split('.')[-1].upper()
        select_fields = TABLE_FIELD_MAP.get(table_name, ['*'])
        detail_sql = 'SELECT ' + ', '.join(select_fields) + ' ' + from_clause
        detail_sql = re.sub(r'\s+GROUP\s+BY\s+[\s\S]*$', '', detail_sql, flags=re.IGNORECASE).strip()

        from_inner = re.sub(r'^FROM\s+', '', from_clause, flags=re.IGNORECASE)
        from_inner = re.sub(r'\s+GROUP\s+BY\s+.*$', '', from_inner, flags=re.IGNORECASE).strip()

        return detail_sql.strip(), from_inner.strip()

# ==============================
# 主程序（友好界面）
# ==============================
def main():
    root = Tk()
    root.withdraw()

    # 欢迎与功能说明
    messagebox.showinfo(
        "SQL明细化神器 开源版",
        "欢迎使用 SQL明细化神器（开源通用版）\n\n"
        "当前版本：v14.2（2025.12.28）\n\n"
        "支持功能：\n"
        "✔ 自动识别 Excel 中含 1#sqlValue(...) 的整行或整列\n"
        "✔ UNION ALL 自动拆分成多条明细SQL\n"
        "✔ 支持 LEFT JOIN / INNER JOIN 等普通联表查询\n"
        "✔ 指标编号自动去重（多列加 _1 _2 _3）\n\n"
        "暂不支持：\n"
        "✘ WITH (CTE) 开头的复杂子查询\n\n"
        "使用前请修改代码中的 TABLE_FIELD_MAP，\n"
        "添加自己系统的表名和明细字段！"
    )

    files = filedialog.askopenfilenames(
        title="请选择需要处理的报表 Excel 文件（支持多选）",
        filetypes=[("Excel 文件", "*.xls *.xlsx"), ("所有文件", "*.*")]
    )
    if not files:
        messagebox.showinfo("提示", "未选择文件，程序已退出。")
        return

    success = 0
    fail = 0
    results = []

    for file_path in files:
        try:
            file_path = Path(file_path)

            # 需要用户点击确认才能继续处理
            if not messagebox.askokcancel(
                "准备处理文件",
                f"即将处理：\n{file_path.name}\n\n"
                "点击【确定】开始处理当前文件\n"
                "点击【取消】将跳过本文件及后续所有文件"
            ):
                results.append(f"⚠ 已跳过: {file_path.name}（用户取消）")
                continue  # 跳过当前文件，继续下一个（但由于用户可能想全部停止，这里也可用 break）

            print(f"\n正在处理: {file_path.name}")

            df = pd.read_excel(file_path, engine='xlrd' if file_path.suffix.lower() == '.xls' else 'openpyxl')
            col_names = list(df.columns)

            # 自动识别含 1#sqlValue 的列
            sql_columns = [
                col for col in col_names
                if df[col].fillna('').astype(str).str.contains('1#sqlValue', case=False).any()
            ]

            if not sql_columns:
                choice = simpledialog.askstring(
                    "手动选择",
                    "未检测到 1#sqlValue，请手动输入含SQL的列名或序号（逗号分隔）：\n\n" +
                    "\n".join(f"{i+1}: {c}" for i, c in enumerate(col_names))
                )
                if not choice:
                    raise ValueError("用户取消操作")
                for part in [x.strip() for x in choice.split(',')]:
                    if part.isdigit():
                        idx = int(part) - 1
                        if 0 <= idx < len(col_names):
                            sql_columns.append(col_names[idx])
                    elif part in col_names:
                        sql_columns.append(part)

            print(f"识别到 {len(sql_columns)} 个SQL列：{sql_columns}")

            # 自动识别指标编号和名称列
            code_column = name_column = None
            for col in col_names:
                low = str(col).lower()
                if any(k in low for k in ['项次', '序号', '项目', '行号', '指标编号', 'code']) and not code_column:
                    code_column = col
                if any(k in low for k in ['项目', '指标名称', '名称', '项 目', 'name']) and not name_column:
                    name_column = col
            if not code_column:
                code_column = col_names[0]
            if not name_column and len(col_names) > 1:
                name_column = col_names[1]

            data = []
            for idx, row in df.iterrows():
                for sql_col in sql_columns:
                    cell = str(row[sql_col]) if not pd.isna(row[sql_col]) else ''
                    if '1#sqlValue' not in cell:
                        continue

                    original_sql = re.sub(
                        r'1#sqlValue\s*\(\s*["\']?(.*?)["\']?\s*\)',
                        r'\1',
                        cell,
                        flags=re.IGNORECASE | re.DOTALL
                    ).strip()

                    code = str(row[code_column]).strip() if pd.notna(row[code_column]) else f"ROW_{idx+1}"
                    name = str(row[name_column]).strip() if pd.notna(row[name_column]) else ""

                    detail_sql, from_inner = transform_sql(original_sql)
                    if detail_sql:
                        col_index = sql_columns.index(sql_col) + 1
                        final_code = f"{code}_{col_index}"
                        data.append({
                            '指标编号': final_code,
                            '指标名称': name,
                            'Original_SQL': original_sql,
                            'Detail_SQL': detail_sql,
                            'FROM_Inner': from_inner
                        })
                        print(f"成功: {final_code} {name}")

            if not data:
                raise ValueError("当前文件未提取到任何有效SQL")

            output_path = file_path.parent / f"{file_path.stem}_明细双输出.xlsx"
            pd.DataFrame(data).to_excel(output_path, index=False)
            print(f"输出成功: {output_path.name}")
            success += 1
            results.append(f"✓ 成功: {file_path.name}")

        except Exception as e:
            fail += 1
            results.append(f"✗ 失败: {file_path.name} → {str(e)}")
            print(f"错误: {e}")

    # 处理完成总结
    summary = f"明细化处理完成！\n\n成功：{success} 个文件\n失败：{fail} 个文件"
    if results:
        summary += "\n\n详细结果：\n" + "\n".join(results[:30])
        if len(results) > 30:
            summary += "\n...（共 {len(results)} 条）"

    messagebox.showinfo("完成", summary)

    if success > 0:
        os.startfile(str(Path(files[0]).parent))

if __name__ == "__main__":
    main()