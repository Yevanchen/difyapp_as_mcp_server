# Dify as MCP Server

将Dify工作流作为Model Context Protocol (MCP)服务器暴露给Claude等AI客户端。

## 项目概述

本项目实现了一个Dify插件，允许将Dify工作流通过Model Context Protocol (MCP)协议暴露给支持该协议的AI客户端（如Claude Desktop、Cursor等）。通过这个插件，您可以：

- 将Dify工作流作为工具提供给Claude等AI
- 让AI客户端能够发现并使用您的工作流
- 无需修改工作流即可集成到AI助手中

## 特性

- ✅ 支持MCP标准的JSON-RPC接口
- ✅ 工具自动发现和注册
- ✅ 与Claude Desktop/Cursor等客户端兼容
- ✅ 安全的SSE连接实现
- ✅ 服务器端会话管理
- 🔄 符合最新的MCP Streamable HTTP规范（基于PR #206）

## 背景

Model Context Protocol (MCP) 是一个开放标准，允许AI模型与外部工具和数据源交互。随着MCP的发展，协议正在从HTTP+SSE模式过渡到新的"Streamable HTTP"传输模式，为无状态服务器提供更好的支持。

本项目跟踪并实现了最新的MCP协议变化，特别是：

- 服务器负责生成和管理会话ID
- 支持无状态服务器模式（适合Dify插件环境）
- 标准化的消息格式和流处理
- 安全的会话管理和身份验证


2. 配置插件设置：
   - **应用ID**: 您想要暴露的Dify应用ID
   - **其他设置**: 根据需要配置

## 使用方法

### 1. 在Dify中配置

确保您的Dify应用包含至少一个工作流，并且已经正确配置。

### 2. 在客户端使用

1. 打开客户端
2. 进入设置 > MCP服务器
3. 添加新的MCP服务器，URL填写：
   ```
   https://您的Dify实例地址/difyapp_as_mcp_server
   ```
4. 保存并启用服务器


### 3. 在Cursor中使用

1. 打开Cursor
2. 进入设置 > AI > MCP
3. 添加服务器地址：
   ```
   https://您的Dify实例地址/difyapp_as_mcp_server
   ```
4. 保存并启用
5. 在Cursor Agent中使用您的工具

## 技术细节

### 架构

本插件使用两个端点实现MCP服务器：

- **GET 端点**: 处理SSE连接和HTML页面
- **POST 端点**: 处理JSON-RPC请求

由于Dify插件环境的限制，我们采用了"最小可行"的SSE实现，包括：

- 服务器端会话ID生成
- 有限心跳模式（约5分钟）
- 客户端断开后自动重连
- 符合最新的Streamable HTTP规范

### 工具注册

工具会自动从Dify工作流中生成，并通过MCP协议暴露给客户端。工具定义包括：

- 名称和描述
- 输入参数定义
- 返回值类型
- 参数验证

### 无状态模式支持

本插件支持符合最新MCP规范的无状态服务器模式，这意味着：

- 服务器不需要维护长期连接
- 每个请求都是独立的
- 通过会话ID关联请求
- 适合Dify的无状态API环境

## 故障排除

1. **连接问题**:
   - 确保URL正确并可以访问
   - 检查是否在防火墙或代理后面

2. **工具不可见**:
   - 确保应用ID配置正确
   - 检查工作流是否已发布
   - 确认Dify API密钥有足够权限

3. **工具执行失败**:
   - 检查Dify应用日志
   - 确认工作流在Dify中可以正常运行

## 贡献

欢迎提交问题和合并请求。在提交代码之前，请确保遵循代码风格并添加适当的测试。

## 许可证

MIT

## 致谢

本项目参考了[Model Context Protocol](https://github.com/modelcontextprotocol/specification)规范，特别是最新的[Streamable HTTP传输PR #206](https://github.com/modelcontextprotocol/specification/pull/206)。

VIBE CODING 探索产物 不可用状态

**Author:** yevanchen
**Version:** 0.0.1
**Type:** extension

### Description



