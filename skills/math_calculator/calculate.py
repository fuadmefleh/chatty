"""Calculator tool for evaluating mathematical expressions."""
import ast
import operator

async def execute(expression: str) -> float:
    """Safely evaluate a mathematical expression.
    
    Args:
        expression: Math expression to evaluate (e.g., '2 + 2', '10 * 5')
    
    Returns:
        Result of the calculation
    """
    # Safe operators
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }
    
    def eval_node(node):
        if isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.BinOp):
            return operators[type(node.op)](eval_node(node.left), eval_node(node.right))
        elif isinstance(node, ast.UnaryOp):
            return operators[type(node.op)](eval_node(node.operand))
        else:
            raise ValueError(f"Unsupported operation: {type(node)}")
    
    tree = ast.parse(expression, mode="eval")
    return eval_node(tree.body)
