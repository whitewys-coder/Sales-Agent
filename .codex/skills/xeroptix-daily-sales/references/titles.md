# 多语言岗位检索词典

只把以下头衔用于检索和初步角色映射；不要把岗位命中当作现任/决策权核实。按词边界和最长匹配处理，CTO不能命中director子串。API是否支持这些值须核真实返回。

## §7 角色簇与七语系头衔词典（本规程最值钱的部分）

### 7.1 10 类角色簇与写信切口

| 代码 | 角色 | 写信切口 |
|---|---|---|
| `PUR` | 采购负责人 | 供应商能力、模块化选配、TCO、**不讲算法** |
| `SRC` | 寻源 / Strategic Sourcing | 新供应商导入、替代方案、成本结构 |
| `SCM` | 供应链负责人 | 交付波动、来料质量、批次追溯 |
| `TECH` | 技术负责人 / CTO | 集成接口、边缘部署、与现有系统共存 |
| `PROD` | 生产线负责人 | 节拍、停机、返工、换型 |
| `PLANT` | 工厂经理 / 厂长 | OEE、产能、跨线一致性 |
| `QA` | 质量负责人 | 漏检率、0 缺陷、审核文件、客户索赔 |
| `ENG` | 工程 / 研发负责人 | 新工艺导入、设备选型、开发周期 |
| `AUTO` | 自动化负责人 | 接口、PLC/机器人集成、改造可行性 |
| `BOSS` | 中小企业老板 | 投入小、见效快、不用招算法团队 |

> 代码里另有 `PARTNER`，**仅东南亚渠道场景使用**。

### 7.2 七语系头衔词典（按国家选对应语言组，直接复制粘贴）

**核心心法**：德国 200 人的 Mittelstand，质量负责人头衔写的是 `Qualitätsleiter`，
不会写 "Head of Quality"。**用当地语言扩大岗位覆盖；不能据此断言这些人从未被联系。**

#### 🇩🇪🇦🇹🇨🇭 德语区（Germany / Austria / 瑞士德语区）

```
PUR   "Einkaufsleiter" OR "Leiter Einkauf" OR "Beschaffungsleiter" OR "Strategischer Einkäufer" OR "Head of Purchasing"
SRC   "Sourcing Manager" OR "Leiter Sourcing" OR "Strategic Sourcing"
SCM   "Supply Chain Manager" OR "Leiter Supply Chain" OR "Logistikleiter"
TECH  "Technischer Leiter" OR "Leiter Technik" OR "Technischer Direktor" OR CTO
PROD  "Produktionsleiter" OR "Fertigungsleiter" OR "Leiter Fertigung" OR "Head of Production"
PLANT "Werksleiter" OR "Betriebsleiter" OR "Standortleiter" OR "Plant Manager"
QA    "Qualitätsleiter" OR "Leiter Qualität" OR "Qualitätsmanager" OR "QS-Leiter" OR "Head of Quality"
ENG   "Entwicklungsleiter" OR "Leiter Engineering" OR "Head of Engineering" OR "Engineering Manager"
AUTO  "Leiter Automatisierung" OR "Automatisierungsleiter" OR "Head of Automation" OR "Leiter Steuerungstechnik"
BOSS  "Geschäftsführer" OR "Inhaber" OR "Managing Director" OR "Vorstand"
```

#### 🇫🇷🇧🇪🇨🇭 法语区（France / 比利时瓦隆 / 瑞士法语区）

```
PUR   "Directeur Achats" OR "Responsable Achats" OR "Acheteur Industriel"
SRC   "Responsable Sourcing" OR "Directeur Sourcing"
SCM   "Directeur Supply Chain" OR "Directeur Logistique"
TECH  "Directeur Technique" OR "Responsable Technique"
PROD  "Directeur de Production" OR "Responsable de Production" OR "Directeur Industriel"
PLANT "Directeur d'Usine" OR "Directeur de Site" OR "Responsable de Site"
QA    "Directeur Qualité" OR "Responsable Qualité" OR "Responsable QSE"
ENG   "Responsable Méthodes" OR "Directeur des Méthodes" OR "Directeur Ingénierie"
AUTO  "Responsable Automatisme" OR "Responsable Automatisation" OR "Chef de Projet Automatisme"
BOSS  "Directeur Général" OR "Gérant" OR "Président"
```

#### 🇪🇸 西班牙

```
PUR   "Director de Compras" OR "Responsable de Compras" OR "Jefe de Compras"
SRC   "Responsable de Sourcing"
SCM   "Director de Supply Chain" OR "Director de Logística"
TECH  "Director Técnico" OR "Responsable Técnico"
PROD  "Director de Producción" OR "Jefe de Producción" OR "Responsable de Producción"
PLANT "Director de Planta" OR "Gerente de Planta" OR "Director de Fábrica"
QA    "Director de Calidad" OR "Responsable de Calidad" OR "Jefe de Calidad"
ENG   "Director de Ingeniería" OR "Jefe de Ingeniería"
AUTO  "Responsable de Automatización" OR "Jefe de Automatización"
BOSS  "Director General" OR "Gerente" OR "Consejero Delegado"
```

#### 🇮🇹 意大利

```
PUR   "Direttore Acquisti" OR "Responsabile Acquisti" OR "Procurement Manager"
SRC   "Responsabile Sourcing"
SCM   "Direttore Supply Chain" OR "Direttore Logistica"
TECH  "Direttore Tecnico" OR "Responsabile Tecnico"
PROD  "Direttore di Produzione" OR "Responsabile di Produzione"
PLANT "Direttore di Stabilimento" OR "Responsabile di Stabilimento"
QA    "Direttore Qualità" OR "Responsabile Qualità" OR "Responsabile Qualità e Ambiente"
ENG   "Responsabile Ufficio Tecnico" OR "Direttore Engineering"
AUTO  "Responsabile Automazione" OR "Responsabile Automazione Industriale"
BOSS  "Amministratore Delegato" OR "Direttore Generale" OR "Titolare"
```

#### 🇳🇱🇧🇪 荷语区（Netherlands / 比利时弗兰德）

```
PUR   "Inkoopmanager" OR "Manager Inkoop" OR "Hoofd Inkoop" OR "Head of Procurement"
SRC   "Sourcing Manager"
SCM   "Supply Chain Manager" OR "Logistiek Manager"
TECH  "Technisch Manager" OR "Hoofd Techniek" OR "Technisch Directeur"
PROD  "Productiemanager" OR "Manager Productie" OR "Hoofd Productie"
PLANT "Fabrieksmanager" OR "Vestigingsmanager"
QA    "Kwaliteitsmanager" OR "Manager Kwaliteit" OR "Hoofd Kwaliteit" OR "QA Manager"
ENG   "Engineering Manager" OR "Hoofd Engineering"
AUTO  "Automation Manager" OR "Manager Automatisering"
BOSS  "Algemeen Directeur" OR "Directeur" OR "Eigenaar"
```

#### 🇭🇺 匈牙利

```
PUR   "Beszerzési vezető" OR "Beszerzési igazgató"
SCM   "Supply Chain vezető" OR "Logisztikai vezető"
TECH  "Műszaki igazgató" OR "Műszaki vezető"
PROD  "Termelési vezető" OR "Gyártási vezető"
PLANT "Gyárigazgató" OR "Üzemvezető"
QA    "Minőségirányítási vezető" OR "Minőségbiztosítási vezető"
ENG   "Mérnökségi vezető" OR "Fejlesztési vezető"
AUTO  "Automatizálási vezető"
BOSS  "Ügyvezető igazgató" OR "Ügyvezető"
```

#### 🇨🇿 捷克

```
PUR   "Vedoucí nákupu" OR "Nákupní ředitel" OR "Nákupní manažer"
SCM   "Logistický ředitel" OR "Supply Chain manažer"
TECH  "Technický ředitel" OR "Technický manažer"
PROD  "Vedoucí výroby" OR "Ředitel výroby" OR "Výrobní manažer"
PLANT "Ředitel závodu" OR "Vedoucí závodu"
QA    "Vedoucí kvality" OR "Manažer kvality" OR "Ředitel kvality"
ENG   "Vedoucí inženýringu" OR "Ředitel inženýringu"
AUTO  "Vedoucí automatizace" OR "Specialista automatizace"
BOSS  "Jednatel" OR "Generální ředitel" OR "Ředitel"
```

---

