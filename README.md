### 开发参考
https://lbsyun.baidu.com/faq/api?title=webapi/uri/andriod

## MCP Usage
```json
{
  "mcpServers": {
    "xiaozhi-baidumap-mcp": {
      "command": "uvx",
      "type": "stdio",
      "args": [
        "--index",
        "https://pypi.mac.axyz.cc:30923/simple",
        "--allow-insecure-host",
        "pypi.mac.axyz.cc",
        "xiaozhi-baidumap-mcp"
      ],
      "env": {}
    }
  }
}
```

### for debug
```json
{
  "mcpServers": {
 "xiaozhi-baidu-map-debug": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/panxuesen/Documents/vscode-code/python/xiaozhi_baidumap_mcp",
        "xiaozhi-baidumap-mcp"
      ],
      "env": {
        "PC_DEBUG": "true"
      }
    }
  }
}
```