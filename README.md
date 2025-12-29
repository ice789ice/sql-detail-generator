# SQL明细化神器（开源通用版）

[![Version](https://img.shields.io/badge/版本-v14.2-blue)](https://github.com/ice789ice/sql-detail-generator/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.8+-green)]()
[![License](https://img.shields.io/badge/许可证-MIT-brightgreen)](LICENSE)

**一键将报表 Excel 中 `1#sqlValue(...)` 自动转换为可执行的明细查询 SQL**

专治：
- 多列表格（同一文件多列含SQL）
- UNION 汇总查询自动拆分
- 指标编号重复（自动加 _1 _2 _3 去重）
- 普通 LEFT JOIN / INNER JOIN 查询

## 功能特点

- 支持自动识别 Excel 中整行或整列出现的 `1#sqlValue(...)`
- 支持 UNION / UNION ALL 自动拆分成多条明细 SQL
- 支持普通多表 JOIN 查询
- 指标编号自动去重，输出清晰
- 极致脱敏，仅提供通用示例，用户可完全自定义明细字段
- 图形化界面，操作简单，无需命令行
- 每个文件处理前弹出确认框，避免误操作

**暂不支持**：WITH (CTE) 开头的复杂子查询

## 转换示例（前后对比）

工具的核心价值：**将原始的汇总/聚合查询快速展开为明细字段查询**，帮助你快速查看底层数据，验证报表结果是否正确。

### 示例 1：余额求和 → 明细展开

**原始报表 SQL**（常见汇总形式）：
```sql
SELECT SUM(A.BALANCE) AS 余额合计
FROM TABLE_ACCOUNT A
WHERE A.DATE = '20251229'
GROUP BY A.ITEM_NO
```
#### 工具自动生成明细 SQL（去掉聚合，直接查明细）：
```sql
SELECT A.DATE,
       A.ORG,
       A.ITEM_NO,
       A.ACCT_NO,
       A.CUST_NO,
       B.CUST_NAME,
       A.CCY,
       A.BALANCE
FROM TABLE_ACCOUNT A
LEFT JOIN CUSTOMER B ON A.CUST_NO = B.CUST_NO
WHERE A.DATE = '20251229'
说明：
你可以直接执行这个明细 SQL，查看每一笔账户余额的原始记录，再自行 SUM(A.BALANCE) 验证是否与报表结果一致。
```
### 示例 2：任意指标求和 → 明细展开（通用场景）
原始报表 SQL：
```sql
SELECT SUM(A.ZZZ) AS 指标合计
FROM YOUR_TABLE A
WHERE A.DATE = '20251229'
GROUP BY A.ITEM_NO
```
#### 工具自动生成明细 SQL（基于字段映射）：
```sql
SELECT A.ZZZ,
       A.XXX,
       A.CCC,
       A.DATE,
       A.ORG,
       A.ITEM_NO,
       A.OTHER_FIELD
FROM YOUR_TABLE A
WHERE A.DATE = '20251229'
说明：
原始 SQL 使用 SUM(A.ZZZ) 等聚合方式，工具会自动：
1.去掉 GROUP BY
2.将 SUM 替换为你配置的明细字段列表
3.从而方便你直接查看底层明细数据。
```
### 示例 3：交易金额求和 → 明细展开
原始报表 SQL：
```sql
SELECT SUM(A.TRANS_AMT) AS 交易金额合计
FROM TA BLE_INCOME A
WHERE A.DATE >= '20250101' AND A.ITEM_NO = '001'
```
工具自动生成明细 SQL：
```sql
SELECT A.DATE,
       A.ORG,
       A.ITEM_NO,
       A.ACCT_NO,
       A.CUST_NO,
       B.CUST_NAME,
       A.TRANS_AMT
FROM TABLE_INCOME A
LEFT JOIN CUSTOMER B ON A.CUST_NO = B.CUST_NO
WHERE A.DATE >= '20250101' AND A.ITEM_NO = '001'
说明：
通过该明细 SQL，可以清晰看到每一笔交易金额，用于核对交易金额汇总是否准确。
```
## 使用方法
下载 exe（推荐，无需安装 Python）
- 前往 Releases 下载最新 exe 文件
- 双击运行 exe
- 进入欢迎界面
- 选择一个 Excel 文件
- 文件会弹出「准备处理文件」确认框，点击【确定】开始处理
- 处理完成后，在原文件同目录生成 xxx_明细双输出.xlsx
### 输出文件内容说明
#### 输出 Excel 中包含以下列：

- 指标编号（自动去重，如 001_1、001_2）
- 指标名称
- Original_SQL（原始报表 SQL）
- Detail_SQL（展开后的明细 SQL，可直接执行）
- FROM_Inner（可用于子查询）
## 自定义明细字段配置（重要）
### 修改 sql_detail_generator.py 文件中的 TABLE_FIELD_MAP(可以增加多个不同主表明细，系统会自动识别)：
``` python
TABLE_FIELD_MAP = {
    'YOUR_TABLE_NAME': [          # SQL 中 FROM 后的表名（需大写）
        'A.DATE',
        'A.ORG',
        'A.ITEM_NO',
        'A.ACCT_NO',
        'A.CUST_NO',
        'B.CUST_NAME',
        'A.CCY',
        'A.ZZZ',                  # 核心指标字段
        'A.XXX',
        'A.CCC',
        # 可继续扩展任意字段 / 表达式 / AS 别名
    ]
}
未匹配到的表会自动保留原 SELECT 或 fallback 到 SELECT *
 ```
### 修改后重新运行sql_detail_generator.py即可生效
## 许可证
MIT License - 允许自由使用、修改、分发及商用。
