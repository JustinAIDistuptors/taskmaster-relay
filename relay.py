#!/usr/bin/env python3
"""
Taskmaster Relay Server
This file implements a relay server for the taskmaster MCP server.
"""

import os
import json
import logging
from functools import lru_cache
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.responses import PlainTextResponse
import httpx
import uvicorn

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("taskmaster-relay")

# Get environment variables
UPSTREAM_URL = os.environ.get("UPSTREAM_URL", "https://taskmaster-mcp.fly.dev")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "taskmaster")
TASKMASTER_PATH = os.environ.get("TASKMASTER_PATH", "/sss")

# Create FastAPI app
app = FastAPI(
    title="Taskmaster Relay",
    description="A relay server for the Taskmaster MCP server",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define OpenAPI schema for taskmaster functions
TASKMASTER_FUNCTIONS = {
    "list_tasks": {
        "description": "List all tasks",
        "parameters": {},
        "example": {
            "function_call": {
                "name": "list_tasks",
                "parameters": {}
            }
        }
    },
    "get_task": {
        "description": "Get a specific task by ID",
        "parameters": {
            "id": {
                "type": "string",
                "description": "Task ID"
            }
        },
        "example": {
            "function_call": {
                "name": "get_task",
                "parameters": {
                    "id": "task-001"
                }
            }
        }
    },
    "create_task": {
        "description": "Create a new task",
        "parameters": {
            "title": {
                "type": "string",
                "description": "Task title"
            },
            "description": {
                "type": "string",
                "description": "Task description"
            },
            "status": {
                "type": "string",
                "description": "Task status (e.g., 'todo', 'in_progress', 'done')"
            },
            "priority": {
                "type": "string",
                "description": "Task priority (e.g., 'low', 'medium', 'high')"
            },
            "due_date": {
                "type": "string",
                "description": "Task due date (ISO format)"
            }
        },
        "example": {
            "function_call": {
                "name": "create_task",
                "parameters": {
                    "title": "New Task",
                    "description": "This is a new task",
                    "status": "todo",
                    "priority": "medium",
                    "due_date": "2025-04-30T00:00:00Z"
                }
            }
        }
    },
    "update_task": {
        "description": "Update an existing task",
        "parameters": {
            "id": {
                "type": "string",
                "description": "Task ID"
            },
            "title": {
                "type": "string",
                "description": "Task title"
            },
            "description": {
                "type": "string",
                "description": "Task description"
            },
            "status": {
                "type": "string",
                "description": "Task status (e.g., 'todo', 'in_progress', 'done')"
            },
            "priority": {
                "type": "string",
                "description": "Task priority (e.g., 'low', 'medium', 'high')"
            },
            "due_date": {
                "type": "string",
                "description": "Task due date (ISO format)"
            }
        },
        "example": {
            "function_call": {
                "name": "update_task",
                "parameters": {
                    "id": "task-001",
                    "status": "in_progress"
                }
            }
        }
    },
    "delete_task": {
        "description": "Delete a task",
        "parameters": {
            "id": {
                "type": "string",
                "description": "Task ID"
            }
        },
        "example": {
            "function_call": {
                "name": "delete_task",
                "parameters": {
                    "id": "task-001"
                }
            }
        }
    }
}

@lru_cache(maxsize=1)
def get_openapi_schema_data():
    """Generate OpenAPI schema for taskmaster functions (cached)"""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Taskmaster API",
            "description": "API for managing tasks",
            "version": "1.0.0"
        },
        "security": [{"none": []}],
        "components": {
            "securitySchemes": {
                "none": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "No authentication required. This API is open."
                }
            }
        },
        "paths": {
            f"/proxy/{function_name}": {
                "post": {
                    "summary": function_info["description"],
                    "security": [{"none": []}],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "function_call": {
                                            "type": "object",
                                            "properties": {
                                                "name": {
                                                    "type": "string",
                                                    "enum": [function_name]
                                                },
                                                "parameters": {
                                                    "type": "object",
                                                    "properties": function_info["parameters"]
                                                }
                                            },
                                            "required": ["name", "parameters"]
                                        }
                                    },
                                    "required": ["function_call"]
                                },
                                "example": function_info["example"]
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object"
                                    }
                                }
                            }
                        }
                    }
                }
            }
            for function_name, function_info in TASKMASTER_FUNCTIONS.items()
        }
    }

@app.get("/openapi.json")
async def get_openapi_schema(request: Request):
    """Return OpenAPI schema for taskmaster functions"""
    schema = get_openapi_schema_data()
    
    # Check if client prefers text format
    accept_header = request.headers.get("accept", "")
    if "text/" in accept_header:
        return Response(content=json.dumps(schema, indent=2), media_type="text/plain; charset=utf-8")
    else:
        return JSONResponse(content=schema, headers={"Content-Type": "application/json"}, gzip=True)

@app.get("/openapi.txt")
async def get_openapi_schema_text():
    """Return OpenAPI schema as plain text for LLM tooling"""
    schema = get_openapi_schema_data()
    return PlainTextResponse(
        content=json.dumps(schema, indent=2),
        headers={"Content-Type": "text/plain; charset=utf-8"}
    )
    

@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint"""
    accept_header = request.headers.get("accept", "")
    if "application/health" in accept_header:
        return Response(status_code=204, media_type="application/health+json")
    else:
        return {"ok": True}

@app.post("/proxy/{endpoint:path}")
async def proxy(endpoint: str, request: Request):
    """Proxy requests to the upstream server"""
    try:
        # Parse request body
        body = await request.body()
        
        # Log the request
        logger.info(f"Received request for endpoint: {endpoint}")
        if body:
            try:
                body_json = json.loads(body)
                logger.info(f"Request body: {body_json}")
            except json.JSONDecodeError:
                logger.warning("Request body is not valid JSON")
        
        # Prepare headers
        headers = dict(request.headers)
        
        # Strip Authorization header to avoid CORS issues
        if "authorization" in headers:
            del headers["authorization"]
        if "Authorization" in headers:
            del headers["Authorization"]
        
        # Forward the request to the upstream server
        async with httpx.AsyncClient() as client:
            upstream_url = f"{UPSTREAM_URL}/mcp/{endpoint}"
            logger.info(f"Forwarding request to: {upstream_url}")
            
            response = await client.post(
                upstream_url,
                content=body,
                headers=headers,
                timeout=30.0
            )
            
            # Log the response
            logger.info(f"Received response with status code: {response.status_code}")
            
            # Return the response
            content = response.content
            response_headers = dict(response.headers)
            
            # Add CORS headers
            response_headers["Access-Control-Allow-Origin"] = "*"
            response_headers["Access-Control-Allow-Credentials"] = "false"
            
            return JSONResponse(
                content=response.json() if content else {},
                status_code=response.status_code,
                headers=response_headers
            )
    except httpx.RequestError as e:
        logger.error(f"Error forwarding request: {str(e)}")
        return JSONResponse(
            content={"error": f"Error forwarding request: {str(e)}"},
            status_code=500,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": "false"
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JSONResponse(
            content={"error": f"Unexpected error: {str(e)}"},
            status_code=500,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": "false"
            }
        )

@app.options("/proxy/{endpoint:path}")
async def options_proxy(endpoint: str):
    """Handle OPTIONS requests for CORS preflight"""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Allow-Credentials": "false",
            "Access-Control-Max-Age": "86400"  # 24 hours
        }
    )

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint that returns HTML documentation"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Taskmaster Relay API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
            h1 { color: #333; }
            h2 { color: #444; margin-top: 30px; }
            pre { background-color: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }
            a { color: #0066cc; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .endpoint { margin-bottom: 20px; }
            .description { margin-bottom: 10px; }
        </style>
    </head>
    <body>
        <h1>Taskmaster Relay API</h1>
        <p>This API provides a relay to the Taskmaster MCP server.</p>
        
        <h2>API Documentation</h2>
        <p>View the full API documentation:</p>
        <ul>
            <li><a href="/openapi.json">OpenAPI Specification (JSON)</a></li>
            <li><a href="/openapi.txt">OpenAPI Specification (Text)</a></li>
        </ul>
        
        <h2>Health Check</h2>
        <div class="endpoint">
            <p class="description">Check if the API is healthy:</p>
            <pre>curl -X GET https://taskmaster-relay.fly.dev/health</pre>
        </div>
        
        <h2>Available Functions</h2>
    """
    
    for function_name, function_info in TASKMASTER_FUNCTIONS.items():
        example = json.dumps(function_info["example"], indent=4)
        html_content += f"""
        <div class="endpoint">
            <h3>{function_name}</h3>
            <p class="description">{function_info["description"]}</p>
            <pre>curl -X POST https://taskmaster-relay.fly.dev/proxy/{function_name} \
    -H "Content-Type: application/json" \
    -d '{json.dumps(function_info["example"])}'</pre>
        </div>
        """
    
    html_content += """
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content, media_type="text/html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    logger.info(f"Starting Taskmaster Relay on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
