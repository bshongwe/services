package config

import (
	"fmt"
	"strings"

	"github.com/spf13/viper"
)

// Config holds application configuration
type Config struct {
	v *viper.Viper
}

// New creates a new Config instance
func New(appName string) *Config {
	v := viper.New()
	
	// Set default configuration
	v.SetConfigName("config")
	v.SetConfigType("yaml")
	v.AddConfigPath(".")
	v.AddConfigPath("./config")
	v.AddConfigPath("/etc/" + appName)
	
	// Enable environment variable support
	v.AutomaticEnv()
	v.SetEnvPrefix(strings.ToUpper(appName))
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	
	return &Config{v: v}
}

// Load reads configuration from file and environment
func (c *Config) Load() error {
	if err := c.v.ReadInConfig(); err != nil {
		// It's okay if config file doesn't exist
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			return fmt.Errorf("failed to read config: %w", err)
		}
	}
	return nil
}

// Get returns the value for the given key
func (c *Config) Get(key string) interface{} {
	return c.v.Get(key)
}

// GetString returns the value for the given key as a string
func (c *Config) GetString(key string) string {
	return c.v.GetString(key)
}

// GetInt returns the value for the given key as an int
func (c *Config) GetInt(key string) int {
	return c.v.GetInt(key)
}

// GetBool returns the value for the given key as a bool
func (c *Config) GetBool(key string) bool {
	return c.v.GetBool(key)
}

// GetStringSlice returns the value for the given key as a slice of strings
func (c *Config) GetStringSlice(key string) []string {
	return c.v.GetStringSlice(key)
}

// Set sets the value for the given key
func (c *Config) Set(key string, value interface{}) {
	c.v.Set(key, value)
}

// SetDefault sets the default value for the given key
func (c *Config) SetDefault(key string, value interface{}) {
	c.v.SetDefault(key, value)
}

// IsSet checks if the key is set
func (c *Config) IsSet(key string) bool {
	return c.v.IsSet(key)
}

// AllSettings returns all settings as a map
func (c *Config) AllSettings() map[string]interface{} {
	return c.v.AllSettings()
}

// LoadWithDefaults loads configuration with default values
func LoadWithDefaults(appName string, defaults map[string]interface{}) (*Config, error) {
	cfg := New(appName)
	
	// Set defaults
	for key, value := range defaults {
		cfg.SetDefault(key, value)
	}
	
	// Load from file and env
	if err := cfg.Load(); err != nil {
		return nil, err
	}
	
	return cfg, nil
}
