-- =====================================================
-- 股票基础信息表（TuShare: stock_basic）
-- =====================================================
CREATE TABLE IF NOT EXISTS trade_cal (
    exchange        TEXT    NOT NULL,  -- 交易所 SSE=上交所, SZSE=深交所
    cal_date        INTEGER    NOT NULL,  -- 日历日期 YYYYMMDD
    is_open         INTEGER NOT NULL,  -- 是否交易 1=交易日, 0=休市
    pretrade_date   INTEGER,              -- 上一个交易日 YYYYMMDD

    -- 复合主键
    PRIMARY KEY (exchange, cal_date)
);

-- =====================================================
-- 股票基础信息表（TuShare: stock_basic）
-- =====================================================
CREATE TABLE stock_basic
(
    ts_code      TEXT PRIMARY KEY, -- 股票代码（如 000001.SZ）
    symbol       TEXT,             -- 股票简码（000001）
    name         TEXT,             -- 股票名称
    area         TEXT,             -- 地域
    industry     TEXT,             -- 行业
    market       TEXT,             -- 市场类型（主板/创业板等）
    list_date    INTEGER,             -- 上市日期
    is_hs        TEXT,             -- 是否沪深港通标的，N否 H沪股通 S深股通
    act_name     TEXT,             -- 实控人名称
    act_ent_type TEXT              -- 实控人企业性质
);

-- =====================================================
-- 日线行情表（TuShare: daily）
-- =====================================================
CREATE TABLE daily
(
    ts_code    TEXT NOT NULL, -- 股票代码
    trade_date INTEGER NOT NULL, -- 交易日期
    open       REAL,          -- 开盘价
    high       REAL,          -- 最高价
    low        REAL,          -- 最低价
    close      REAL,          -- 收盘价
    pre_close  REAL,          -- 昨收价
    change     REAL,          -- 涨跌额
    pct_chg    REAL,          -- 涨跌幅（基于除权后的昨收计算的涨跌幅：（今收-除权昨收）/除权昨收）（%）
    vol        REAL,          -- 成交量（手）
    amount     REAL,          -- 成交额（千元）
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX idx_daily_date ON daily (trade_date);

-- =====================================================
-- 复权因子表（TuShare: adj_factor）
-- =====================================================
CREATE TABLE adj_factor
(
    ts_code    TEXT NOT NULL, -- 股票代码
    trade_date INTEGER NOT NULL, -- 交易日期
    adj_factor REAL,          -- 复权因子
    PRIMARY KEY (ts_code, trade_date)
);

-- =====================================================
-- 每日基础指标表（TuShare: daily_basic）
-- =====================================================
CREATE TABLE daily_basic
(
    ts_code         TEXT NOT NULL, -- 股票代码
    trade_date      INTEGER NOT NULL, -- 交易日期
    close           REAL,          -- 收盘价
    turnover_rate   REAL,          -- 换手率（%）
    turnover_rate_f REAL,          -- 换手率（自由流通股）
    volume_ratio    REAL,          -- 量比
    pe              REAL,          -- 市盈率
    pe_ttm          REAL,          -- 市盈率 TTM
    pb              REAL,          -- 市净率
    ps              REAL,          -- 市销率
    ps_ttm          REAL,          -- 市销率（TTM）
    dv_ratio        REAL,          -- 股息率 （%）
    dv_ttm          REAL,          -- 股息率（TTM）（%）
    total_share     REAL,          -- 总股本 （万股）
    float_share     REAL,          -- 流通股本 （万股）
    free_share      REAL,          -- 自由流通股本 （万）
    total_mv        REAL,          -- 总市值（万元）
    circ_mv         REAL,          -- 流通市值（万元）
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX idx_daily_basic_date ON daily_basic (trade_date);

-- =====================================================
-- 指数基础信息表（TuShare: index_basic）
-- =====================================================
CREATE TABLE index_basic
(
    ts_code     TEXT PRIMARY KEY, -- 指数代码
    -- 基本信息
    name        TEXT NOT NULL,    -- 简称
    fullname    TEXT,             -- 指数全称
    market      TEXT,             -- 市场
    publisher   TEXT,             -- 发布方
    index_type  TEXT,             -- 指数风格（如：规模指数、行业指数等）
    category    TEXT,             -- 指数类别

    -- 技术参数
    base_date   INTEGER,             -- 基期（
    base_point  REAL,             -- 基点（改用DECIMAL保证精度）
    list_date   INTEGER,             -- 发布日期

    -- 规则信息
    weight_rule TEXT,             -- 加权方式（如：市值加权、等权等）

    -- 描述信息
    description TEXT,             -- 描述（desc是SQL关键字，改为description）

    -- 有效期信息
    exp_date    INTEGER              -- 终止日期（改为TEXT类型，NULL表示仍在用）
);

-- =====================================================
-- 指数日行情表（TuShare: index_daily）
-- =====================================================
CREATE TABLE index_daily
(
    ts_code    TEXT NOT NULL, -- 股票代码
    trade_date INTEGER NOT NULL, -- 交易日期
    open       REAL,          -- 开盘价
    high       REAL,          -- 最高价
    low        REAL,          -- 最低价
    close      REAL,          -- 收盘价
    pre_close  REAL,          -- 昨收价
    change     REAL,          -- 涨跌额
    pct_chg    REAL,          -- 涨跌幅（基于除权后的昨收计算的涨跌幅：（今收-除权昨收）/除权昨收）（%）
    vol        REAL,          -- 成交量（手）
    amount     REAL,          -- 成交额（千元）
    PRIMARY KEY (ts_code, trade_date)
);

-- =====================================================
-- 指数成分权重表（TuShare: index_weight）
-- =====================================================
CREATE TABLE index_weight
(
    index_code TEXT NOT NULL, -- 指数代码
    con_code   TEXT NOT NULL, -- 成分股代码
    trade_date INTEGER NOT NULL, -- 调整日期
    weight     REAL,          -- 权重
    PRIMARY KEY (index_code, con_code, trade_date)
);

-- =====================================================
-- 利润表（TuShare: income）
-- =====================================================
CREATE TABLE IF NOT EXISTS income (
    ts_code TEXT NOT NULL,                 -- TS代码
    ann_date INTEGER,                          -- 公告日期
    f_ann_date INTEGER,                        -- 实际公告日期
    end_date INTEGER,                          -- 报告期
    report_type TEXT,                       -- 报告类型
    comp_type TEXT,                         -- 公司类型(1一般工商业2银行3保险4证券)
    end_type TEXT,                          -- 报告期类型

    basic_eps REAL,                         -- 基本每股收益
    diluted_eps REAL,                       -- 稀释每股收益

    total_revenue REAL,                     -- 营业总收入
    revenue REAL,                           -- 营业收入
    int_income REAL,                        -- 利息收入
    prem_earned REAL,                       -- 已赚保费
    comm_income REAL,                       -- 手续费及佣金收入
    n_commis_income REAL,                   -- 手续费及佣金净收入
    n_oth_income REAL,                      -- 其他经营净收益
    n_oth_b_income REAL,                    -- 其他业务净收益
    prem_income REAL,                       -- 保险业务收入
    out_prem REAL,                          -- 分出保费
    une_prem_reser REAL,                    -- 提取未到期责任准备金
    reins_income REAL,                      -- 分保费收入

    n_sec_tb_income REAL,                   -- 代理买卖证券业务净收入
    n_sec_uw_income REAL,                   -- 证券承销业务净收入
    n_asset_mg_income REAL,                 -- 受托客户资产管理业务净收入
    oth_b_income REAL,                      -- 其他业务收入

    fv_value_chg_gain REAL,                 -- 公允价值变动净收益
    invest_income REAL,                     -- 投资净收益
    ass_invest_income REAL,                 -- 对联营企业和合营企业投资收益
    forex_gain REAL,                        -- 汇兑净收益

    total_cogs REAL,                        -- 营业总成本
    oper_cost REAL,                         -- 营业成本
    int_exp REAL,                           -- 利息支出
    comm_exp REAL,                          -- 手续费及佣金支出
    biz_tax_surchg REAL,                    -- 税金及附加
    sell_exp REAL,                          -- 销售费用
    admin_exp REAL,                         -- 管理费用
    fin_exp REAL,                           -- 财务费用
    assets_impair_loss REAL,                -- 资产减值损失

    prem_refund REAL,                       -- 退保金
    compens_payout REAL,                    -- 赔付支出
    reser_insur_liab REAL,                  -- 提取保险责任准备金
    div_payt REAL,                          -- 保户红利支出
    reins_exp REAL,                         -- 分保费用
    oper_exp REAL,                          -- 营业支出

    compens_payout_refu REAL,               -- 摊回赔付支出
    insur_reser_refu REAL,                  -- 摊回保险责任准备金
    reins_cost_refund REAL,                 -- 摊回分保费用
    other_bus_cost REAL,                    -- 其他业务成本

    operate_profit REAL,                    -- 营业利润
    non_oper_income REAL,                   -- 营业外收入
    non_oper_exp REAL,                      -- 营业外支出
    nca_disploss REAL,                      -- 非流动资产处置损失

    total_profit REAL,                      -- 利润总额
    income_tax REAL,                        -- 所得税费用
    n_income REAL,                          -- 净利润(含少数股东)
    n_income_attr_p REAL,                   -- 归母净利润
    minority_gain REAL,                     -- 少数股东损益

    oth_compr_income REAL,                  -- 其他综合收益
    t_compr_income REAL,                    -- 综合收益总额
    compr_inc_attr_p REAL,                  -- 归母综合收益
    compr_inc_attr_m_s REAL,                -- 少数股东综合收益

    ebit REAL,                              -- EBIT
    ebitda REAL,                            -- EBITDA

    insurance_exp REAL,                     -- 保险业务支出
    undist_profit REAL,                     -- 年初未分配利润
    distable_profit REAL,                   -- 可分配利润
    rd_exp REAL,                            -- 研发费用

    fin_exp_int_exp REAL,                   -- 财务费用-利息费用
    fin_exp_int_inc REAL,                   -- 财务费用-利息收入

    transfer_surplus_rese REAL,             -- 盈余公积转入
    transfer_housing_imprest REAL,           -- 住房周转金转入
    transfer_oth REAL,                      -- 其他转入
    adj_lossgain REAL,                      -- 调整以前年度损益

    withdra_legal_surplus REAL,              -- 提取法定盈余公积
    withdra_legal_pubfund REAL,              -- 提取法定公益金
    withdra_biz_devfund REAL,                -- 提取企业发展基金
    withdra_rese_fund REAL,                  -- 提取储备基金
    withdra_oth_ersu REAL,                   -- 提取任意盈余公积

    workers_welfare REAL,                   -- 职工福利
    distr_profit_shrhder REAL,               -- 可供股东分配利润
    prfshare_payable_dvd REAL,               -- 应付优先股股利
    comshare_payable_dvd REAL,               -- 应付普通股股利
    capit_comstock_div REAL,                 -- 转作股本普通股股利

    net_after_nr_lp_correct REAL,            -- 扣非净利润（更正前）
    credit_impa_loss REAL,                  -- 信用减值损失
    net_expo_hedging_benefits REAL,          -- 净敞口套期收益
    oth_impair_loss_assets REAL,             -- 其他资产减值损失
    total_opcost REAL,                      -- 营业总成本（二）
    amodcost_fin_assets REAL,                -- 金融资产终止确认收益
    oth_income REAL,                        -- 其他收益
    asset_disp_income REAL,                 -- 资产处置收益
    continued_net_profit REAL,              -- 持续经营净利润
    end_net_profit REAL,                    -- 终止经营净利润

    update_flag TEXT,                       -- 更新标识

    PRIMARY KEY (ts_code, end_date, report_type)
);
--
--
-- -- =====================================================
-- -- 资产负债表（TuShare: balancesheet）
-- -- =====================================================
-- CREATE TABLE balance_sheet
-- (
--     ts_code      TEXT NOT NULL, -- 股票代码
--     end_date     INTEGER        NOT NULL, -- 报告期
--     total_assets REAL,       -- 资产总计
--     total_liab   REAL,       -- 负债合计
--     total_equity REAL,       -- 股东权益合计
--     PRIMARY KEY (ts_code, end_date)
-- );
--
-- -- =====================================================
-- -- 现金流量表（TuShare: cashflow）
-- -- =====================================================
-- CREATE TABLE cashflow
-- (
--     ts_code        TEXT NOT NULL, -- 股票代码
--     end_date       INTEGER        NOT NULL, -- 报告期
--     n_cashflow_act REAL,       -- 经营活动现金流量净额
--     free_cashflow  REAL,       -- 自由现金流
--     PRIMARY KEY (ts_code, end_date)
-- );
--
-- -- =====================================================
-- -- 财务指标表（TuShare: fina_indicator）
-- -- =====================================================
-- CREATE TABLE fina_indicator
-- (
--     ts_code            TEXT NOT NULL, -- 股票代码
--     end_date           INTEGER        NOT NULL, -- 报告期
--     roe                REAL,       -- 净资产收益率
--     roa                REAL,       -- 总资产收益率
--     grossprofit_margin REAL,       -- 毛利率
--     netprofit_margin   REAL,       -- 净利率
--     debt_to_assets     REAL,       -- 资产负债率
--     PRIMARY KEY (ts_code, end_date)
-- );
--
-- =====================================================
-- 停复牌信息表（TuShare: suspend）
-- =====================================================
CREATE TABLE suspend
(
    ts_code      TEXT NOT NULL, -- 股票代码
    trade_date INTEGER        NOT NULL, -- 停复牌日期
    suspend_timing  TEXT,                 -- 日内停牌时间段
    suspend_type       TEXT,                 -- 停复牌类型：S-停牌，R-复牌
    PRIMARY KEY (ts_code, trade_date)
);
--
-- =====================================================
-- 涨跌停信息表（TuShare: limit_list）
-- =====================================================
CREATE TABLE stk_limit
(
    ts_code    TEXT NOT NULL, -- 股票代码
    trade_date INTEGER        NOT NULL, -- 交易日期
    pre_close REAL,                 -- 昨日收盘价
    up_limit REAL,                 -- 涨停价
    down_limit REAL,                 -- 跌停价
    PRIMARY KEY (ts_code, trade_date)
);
--
-- -- =====================================================
-- -- 股东人数表（TuShare: stk_holdernumber）
-- -- =====================================================
-- CREATE TABLE holder_number
-- (
--     ts_code    TEXT NOT NULL, -- 股票代码
--     end_date   INTEGER        NOT NULL, -- 截止日期
--     holder_num INTEGER,              -- 股东户数
--     PRIMARY KEY (ts_code, end_date)
-- );

-- =====================================================
-- 数据版本管理表（自定义）
-- =====================================================
CREATE TABLE data_version
(
    table_name   TEXT PRIMARY KEY, -- 表名
    last_upTEXT  TEXT,             -- 最近更新时间
    record_count INTEGER           -- 当前记录数
);
