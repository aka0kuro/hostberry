package main

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/yuin/gopher-lua"
)

// LuaEngine maneja la ejecución de scripts Lua
type LuaEngine struct {
	L      *lua.LState
	ScriptsPath string
}

// NewLuaEngine crea una nueva instancia del motor Lua
func NewLuaEngine(scriptsPath string) (*LuaEngine, error) {
	L := lua.NewState()
	defer L.Close()

	// Verificar que el directorio de scripts existe
	if _, err := os.Stat(scriptsPath); os.IsNotExist(err) {
		return nil, fmt.Errorf("directorio de scripts no existe: %s", scriptsPath)
	}

	engine := &LuaEngine{
		L:          lua.NewState(),
		ScriptsPath: scriptsPath,
	}

	// Registrar funciones Go en Lua
	engine.registerFunctions()

	return engine, nil
}

// registerFunctions registra funciones de Go que pueden ser llamadas desde Lua
func (le *LuaEngine) registerFunctions() {
	// Función para ejecutar comandos del sistema
	le.L.SetGlobal("exec", le.L.NewFunction(func(L *lua.LState) int {
		cmd := L.CheckString(1)
		result, err := executeCommandFromLua(cmd)
		if err != nil {
			L.Push(lua.LNil)
			L.Push(lua.LString(err.Error()))
			return 2
		}
		L.Push(lua.LString(result))
		L.Push(lua.LNil)
		return 2
	}))

	// Función para leer archivos
	le.L.SetGlobal("read_file", le.L.NewFunction(func(L *lua.LState) int {
		path := L.CheckString(1)
		data, err := os.ReadFile(path)
		if err != nil {
			L.Push(lua.LNil)
			L.Push(lua.LString(err.Error()))
			return 2
		}
		L.Push(lua.LString(string(data)))
		L.Push(lua.LNil)
		return 2
	}))

	// Función para escribir archivos
	le.L.SetGlobal("write_file", le.L.NewFunction(func(L *lua.LState) int {
		path := L.CheckString(1)
		content := L.CheckString(2)
		err := os.WriteFile(path, []byte(content), 0644)
		if err != nil {
			L.Push(lua.LString(err.Error()))
			return 1
		}
		L.Push(lua.LNil)
		return 1
	}))

	// Función para logging
	le.L.SetGlobal("log", le.L.NewFunction(func(L *lua.LState) int {
		level := L.CheckString(1)
		message := L.CheckString(2)
		fmt.Printf("[LUA %s] %s\n", level, message)
		return 0
	}))

	// Función para obtener variables de entorno
	le.L.SetGlobal("getenv", le.L.NewFunction(func(L *lua.LState) int {
		key := L.CheckString(1)
		value := os.Getenv(key)
		L.Push(lua.LString(value))
		return 1
	}))
}

// Execute ejecuta un script Lua y retorna el resultado
func (le *LuaEngine) Execute(scriptName string, params map[string]interface{}) (map[string]interface{}, error) {
	scriptPath := filepath.Join(le.ScriptsPath, scriptName)
	
	// Verificar que el script existe
	if _, err := os.Stat(scriptPath); os.IsNotExist(err) {
		return nil, fmt.Errorf("script no encontrado: %s", scriptPath)
	}

	// Cargar parámetros en Lua
	if params != nil {
		table := le.L.NewTable()
		for k, v := range params {
			switch val := v.(type) {
			case string:
				table.RawSetString(k, lua.LString(val))
			case int:
				table.RawSetString(k, lua.LNumber(val))
			case float64:
				table.RawSetString(k, lua.LNumber(val))
			case bool:
				table.RawSetString(k, lua.LBool(val))
			case map[string]interface{}:
				subTable := le.L.NewTable()
				for sk, sv := range val {
					subTable.RawSetString(sk, lua.LString(fmt.Sprintf("%v", sv)))
				}
				table.RawSetString(k, subTable)
			}
		}
		le.L.SetGlobal("params", table)
	}

	// Ejecutar script
	if err := le.L.DoFile(scriptPath); err != nil {
		return nil, fmt.Errorf("error ejecutando script Lua: %v", err)
	}

	// Obtener resultado de la variable global "result"
	resultTable := le.L.GetGlobal("result")
	if resultTable == lua.LNil {
		return map[string]interface{}{"success": true}, nil
	}

	// Convertir tabla Lua a map Go
	result := make(map[string]interface{})
	if tbl, ok := resultTable.(*lua.LTable); ok {
		tbl.ForEach(func(key lua.LValue, value lua.LValue) {
			keyStr := key.String()
			result[keyStr] = convertLuaValue(value)
		})
	}

	return result, nil
}

// isArray verifica si una tabla Lua es un array (índices numéricos consecutivos desde 1)
func isArray(tbl *lua.LTable) bool {
	maxNumericKey := 0
	hasStringKeys := false
	tbl.ForEach(func(key lua.LValue, value lua.LValue) {
		if numKey, ok := key.(lua.LNumber); ok {
			if int(numKey) > maxNumericKey {
				maxNumericKey = int(numKey)
			}
		} else {
			hasStringKeys = true
		}
	})
	// Si tiene claves de string, no es un array puro
	if hasStringKeys {
		return false
	}
	// Si el máximo índice numérico es igual al número de elementos, es un array
	return maxNumericKey > 0
}

// convertLuaTableToArray convierte una tabla Lua a un array de Go
func convertLuaTableToArray(tbl *lua.LTable) []interface{} {
	var array []interface{}
	tbl.ForEach(func(key lua.LValue, value lua.LValue) {
		if numKey, ok := key.(lua.LNumber); ok {
			idx := int(numKey) - 1 // Lua usa índices base 1
			if idx >= 0 {
				// Asegurar que el array tenga el tamaño suficiente
				for len(array) <= idx {
					array = append(array, nil)
				}
				array[idx] = convertLuaValue(value)
			}
		}
	})
	return array
}

// convertLuaTableToMap convierte una tabla Lua a un mapa de Go
func convertLuaTableToMap(tbl *lua.LTable) map[string]interface{} {
	subMap := make(map[string]interface{})
	tbl.ForEach(func(k lua.LValue, val lua.LValue) {
		keyStr := k.String()
		subMap[keyStr] = convertLuaValue(val)
	})
	return subMap
}

// convertLuaValue convierte un valor Lua a un valor Go
func convertLuaValue(value lua.LValue) interface{} {
	switch v := value.(type) {
	case lua.LString:
		return string(v)
	case lua.LNumber:
		return float64(v)
	case lua.LBool:
		return bool(v)
	case *lua.LTable:
		// Verificar si es array o mapa
		if isArray(v) {
			return convertLuaTableToArray(v)
		}
		return convertLuaTableToMap(v)
	default:
		return v.String()
	}
}

// Close cierra el motor Lua
func (le *LuaEngine) Close() {
	if le.L != nil {
		le.L.Close()
	}
}

// executeCommandFromLua ejecuta un comando de forma segura (llamado desde Lua)
func executeCommandFromLua(cmd string) (string, error) {
	// Usar la función de utils.go que valida comandos
	return executeCommand(cmd)
}
