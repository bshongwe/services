# Shared Config Package

Viper-based configuration helpers for microservices.

## Features

- ✅ YAML configuration file support
- ✅ Environment variable override
- ✅ Multiple config paths support
- ✅ Type-safe getters
- ✅ Default values support

## Usage

### Basic Usage

```go
package main

import (
    "log"
    "github.com/your-org/platform-services/shared/config"
)

func main() {
    cfg := config.New("myapp")
    
    // Set defaults
    cfg.SetDefault("server.port", 8080)
    cfg.SetDefault("database.host", "localhost")
    
    // Load configuration
    if err := cfg.Load(); err != nil {
        log.Fatal(err)
    }
    
    // Get values
    port := cfg.GetInt("server.port")
    dbHost := cfg.GetString("database.host")
}
```

### With Defaults

```go
defaults := map[string]interface{}{
    "server.port": 8080,
    "server.host": "0.0.0.0",
    "database.host": "localhost",
    "database.port": 5432,
}

cfg, err := config.LoadWithDefaults("myapp", defaults)
if err != nil {
    log.Fatal(err)
}
```

## Configuration Precedence

1. Environment variables (highest priority)
2. Configuration file (YAML)
3. Default values (lowest priority)

## Environment Variables

Environment variables are automatically supported with the following format:

```bash
# For app name "myapp" and key "server.port"
export MYAPP_SERVER_PORT=8080

# For nested keys, use underscores
export MYAPP_DATABASE_HOST=localhost
export MYAPP_DATABASE_PORT=5432
```

## Configuration File

Create a `config.yaml` file:

```yaml
server:
  port: 8080
  host: 0.0.0.0

database:
  host: localhost
  port: 5432
  name: mydb
  
logging:
  level: info
  format: json
```

The config package looks for `config.yaml` in:
- Current directory (`.`)
- `./config` directory
- `/etc/{appname}` directory

## Example: Auth Service Integration

```go
package main

import (
    "log"
    "github.com/your-org/platform-services/shared/config"
)

func main() {
    // Create config with defaults
    cfg, err := config.LoadWithDefaults("auth-service", map[string]interface{}{
        "server.port": 8080,
        "database.host": "localhost",
        "database.port": 5432,
        "database.name": "auth_db",
        "jwt.secret": "change-me-in-production",
        "jwt.expiry": "24h",
    })
    if err != nil {
        log.Fatal(err)
    }
    
    // Use configuration
    port := cfg.GetInt("server.port")
    dbHost := cfg.GetString("database.host")
    jwtSecret := cfg.GetString("jwt.secret")
    
    // Start your service...
}
```

## API Reference

### Creating Config

- `New(appName string) *Config` - Create new config instance
- `LoadWithDefaults(appName string, defaults map[string]interface{}) (*Config, error)` - Load with defaults

### Reading Values

- `Get(key string) interface{}` - Get raw value
- `GetString(key string) string` - Get string value
- `GetInt(key string) int` - Get integer value
- `GetBool(key string) bool` - Get boolean value
- `GetStringSlice(key string) []string` - Get string slice

### Setting Values

- `Set(key string, value interface{})` - Set value
- `SetDefault(key string, value interface{})` - Set default value

### Utilities

- `IsSet(key string) bool` - Check if key is set
- `AllSettings() map[string]interface{}` - Get all settings
- `Load() error` - Load configuration
