# 共识中的FIDO2

**协议级生物识别验证**
**Montana协议 v1.0**

---

## 摘要

Montana — 第一个将生物识别验证（FIDO2/WebAuthn）直接集成到共识中的区块链。Verified User必须物理确认存在（触摸）并通过生物识别（指纹/面部）才能参与区块生产。

**关键区别:**
```
其他区块链: 私钥 = 投票权
Montana: 私钥 + 生物识别 = 投票权
```

---

## 1. 引言

### 1.1 密钥问题

| 系统 | 授权 | 问题 |
|------|------|------|
| 比特币 | 私钥 | 密钥可被盗 |
| 以太坊 | 私钥 | 密钥可被复制 |
| 交易所 | 2FA (TOTP) | 种子可被盗 |
| **Montana** | **FIDO2 + 密钥** | **需要指纹/面部** |

### 1.2 Montana解决方案

Verified User（20%共识）需要两个因素：
1. 私钥（你拥有的东西）
2. 生物识别（你本身的东西）

---

## 2. 架构

### 2.1 共识中的FIDO2标志

**源代码:** [consensus.rs#L382-L389](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/consensus.rs#L382-L389)

```rust
// User Present (UP) — 物理触摸设备
if flags & 0x01 == 0 {
    return Err(PresenceError::Fido2UserNotPresent);
}

// User Verified (UV) — 生物识别（指纹/面部）
if flags & 0x04 == 0 {
    return Err(PresenceError::Fido2UserNotVerified);
}
```

### 2.2 两级节点

| 级别 | 验证 | 共识份额 |
|------|------|----------|
| Full Node | 仅密钥 | 80% |
| Verified User | 密钥 + FIDO2 | 20% |

---

## 3. 验证协议

### 3.1 证明流程

```
┌─────────────────────────────────────────────────────────────┐
│  1. 节点从网络接收挑战                                       │
│  2. 用户触摸设备 (UP=1)                                      │
│  3. 设备验证指纹/面部 (UV=1)                                 │
│  4. 安全芯片签署证明                                         │
│  5. 节点发送签名的存在证明                                   │
│  6. 网络验证UP和UV标志                                       │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 随机间隔（反机器人）

**源代码:** [consensus.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/consensus.rs)

```rust
// Verified User必须确认存在
// 在10-40分钟窗口内的随机时刻
// 机器人无法预测何时
```

---

## 4. 攻击防护

| 攻击 | 防御 | 机制 |
|------|------|------|
| 密钥盗窃 | 需要生物识别 | UV标志必需 |
| 远程机器人 | 需要触摸 | UP标志必需 |
| 重放攻击 | 挑战-响应 | 每次新挑战 |
| 假设备 | 安全芯片 | 硬件证明 |

---

## 5. 科学创新

1. **共识中的FIDO2** — 第一个协议级生物识别的区块链
2. **双因素共识** — 密钥 + 生物识别获得投票权
3. **反机器人** — 随机间隔使自动化不可能
4. **80/20混合** — 无生物识别的服务器 + 有生物识别的人类

---

## 6. 参考文献

| 文档 | 链接 |
|------|------|
| 共识代码 | [consensus.rs](https://github.com/efir369999/junomontanaagibot/blob/main/Montana%20ACP/montana/src/consensus.rs) |
| FIDO2规范 | [WebAuthn W3C](https://www.w3.org/TR/webauthn-2/) |
| ACP共识 | [001_ACP.md](001_ACP.md) |

---

```
Alejandro Montana
Montana协议 v1.0
2026年1月

github.com/efir369999/junomontanaagibot
```
