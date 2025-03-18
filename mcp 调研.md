MCP 调研
结论
1. MCP可以做为Dify工具体系的拓展，与Plugin成为工具中并列的两种类型（MCP作为生态的一部分，与插件并列）
2. Dify客户端可作为MCP Host，MCP Server可作为Dify中的工具
3. Dify工具可发布为MCP Server，在MCP Client中使用
MCP是什么
介绍
MCP(Model Context Protocol ) is an open protocol that standardizes how applications provide context to LLMs.
MCP follows a client-server architecture where a host application can connect to multiple servers
简单来说，MCP是一个CS架构的协议，其目的是为了让模型能够获取到更多的环境信息（上下文）。
协议具体长啥样
[图片]
整体来说，MCP包括以下部分的内容：
- MCP Hosts：想要通过MCP访问数据的程序，如Claude Desktop、IDE或AI工具
- MCP Clients：与服务器维持1:1连接的协议客户端
- MCP Servers：通过标准化的Model Context Protocol公开特定功能的轻量级程序
- Local Data Sources：MCP服务器可以安全访问的计算机文件、数据库和服务
- Remote Services：MCP服务器可以连接的通过互联网可用的外部系统（例如，通过API）
具体来说，一个MCP Client与一个MCP Server相连，通过MCP的传输协议来进行通信
[图片]
连接的生命周期
1. 连接初始化
[图片]
2. 信息交换
- Request-Response: Client发送Request，Server回复Response
- Notifications: Client或者Server也都可以发送单向的信息
3. 断开连接
Client端和Server端都可以进行断开连接
- 客户端通过close()函数来断开连接
- 传输断开
- 产生错误
Server长啥样
根据Transport的类型不同，Server分为两类：Stdio transport和HTTP with SSE transport
1. Stdio transport
使用标准的输入输出进行通信，一般用于用于本地进程
常见的用例：
Client: Claude客户端
Server: 脚本文件
使用：
1. 创建Server
[图片]
2.  配置Server
[图片]
3. 运行
[图片]
2. HTTP with SSE transport
使用HTTP POST方法来进行通信，Dify作为Client主要使用的方法
使用：
1. 前往https://mcp.composio.dev/notion/attractive-fresh-egypt-zkfePp获取Server地址
[图片]
2. 填写对应的Server，这里使用Cursor作为Client
[图片]
3. 在Cursor Agent中使用
[图片]
Client长啥样
Client只要能够遵循MCP的协议，能够与Server建立通信即可
常见的MCP Client
- 客户端（Claude(只支持stdio server)、Cursor）
- IDE插件（Cline、Continue）
- 本地脚本（MCP示例中的聊天机器人）
- Web应用（Dify?）
Q&A
Q: MCP与Agent的关系？
Server可以做为Agent架构中的Tool进行使用，Client可以实现Agent的核心逻辑如Function Call、ReAct等。大部分Host只有Agent中可以使用Server，当然在Dify上我们也可以在Workflow中进行使用。
Q: 接入MCP，对Dify有什么好处？
MCP是一个更大的生态，我们可以参与到这个生态中，可以让Dify的Workflow能够使用更多的工具。同时在Dify中的工作流/工具/应用，可以有更广泛的用途，可以不光只在Dify客户端中使用
Q: 其它产品是怎么接入MCP的？
1. Cursor作为MCP Client，可以连接SSE Server和Stdio Server
[图片]
2. Claude作为MCP Client，但是只能连接Stdio Server
[图片]
3. Composio作为Server的市场，对外提供Server
[图片]
MCP的后续功能规划
目前的MCP定义的内容还不够多，有些问题还是没有很好的解决，导致我们的产品形态会受限。这些预计在25年上半年会进行提供：
1. Server Auth，目前没有提供标准的鉴权协议，导致Auth都是由Server自己来实现的
2. Server分散，现在的Client是不能主动去找哪里有Server可进行连接的，只能自己去一家家的对，即缺少一个Marketplace
3. Stateless and short-lived connection，MCP现阶段是一个有状态，需要进行长连接的协议，如果这部分不进行修改，Dify作为Client就需要一个与Server保持长连接的网关，Dify导出的Server比较难去做Serveless的部署
https://modelcontextprotocol.io/development/roadmap
MCP与Dify结合
整体架构
1. 工具目前支持Plugin、Workflow、Custom这三种，对于工具扩展，我们可以加入MCP类型
2. 由于目前的MCP协议中，都是长连接和有状态的，所以此处预计会设计一个网关服务（待讨论是否可以复用daemon服务）
3. 关于Server这部分，我们认为工具都可以导出为Server，即Plugin、Workflow、API Tool都可以作为Server导出，此处待验证
[图片]
[图片]
用户旅程
Client端
暂时无法在飞书文档外展示此内容
Server端
目前我们可以通过Dify APP中的API加上一个wrapper导出为一个SSE Server
1. 我们导出一个工作流的API
[图片]
2. 配置进Claude中
[图片]
3. 使用
[图片]
待讨论项
Dify作为MCP Client
存在的问题
- 🤔大量的Server是stdio形式的，在Dify中无法使用
- 🤔MCP Server目前缺少一个类似MarketPlace的地方，会不会存在用户不知道在哪找Server的问题
待决策
- ❓我们是否能复用Daemon服务作为MCP的Client网关
- ❓是否需要提供一个中继器，以让用户的Stdio Server转为SSE Server以在Dify中使用
Dify工具作为MCP Server
存在的问题
- 🤔MCP协议现在定义没有标准的鉴权形式，工具的鉴权都是由Server端实现的，我们是否可以参考Composio的设计，后续如果MCP提供了标准的鉴权协议后再接入
Composio的鉴权方式：
[图片]
[图片]
待决策
- ❓在SaaS版本中，工具作为Server导出后，如何限制使用量，防止被白嫖（是否应该是一个收费点）
- ❓Servers的导出形式待验证，是导出一个SSE Server就够了？还是可以通过Docker或者JS/Python Pacakge等方式导出为一个Stdio Server
- ❓Server导出的粒度？是APP还是工具，还是都可以
- ❓插件（Python Code）是否需要提供一个导出为Stdio Server的方法
相关材料
1. MCP协议：https://modelcontextprotocol.io/
2. MCP Servers仓库：https://github.com/modelcontextprotocol/servers
3. Composio Servers: https://mcp.composio.dev/