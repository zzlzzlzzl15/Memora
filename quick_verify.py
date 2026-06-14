#!/usr/bin/env python3
"""
快速验证脚本 - 检查 MinerU 和知识图谱集成是否成功
"""
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))


def check_imports():
    """检查依赖导入"""
    print("=" * 60)
    print("1. 检查依赖导入")
    print("=" * 60)
    
    checks = [
        ("magic-pdf (MinerU)", "magic_pdf"),
        ("neo4j", "neo4j"),
        ("qdrant-client", "qdrant_client"),
    ]
    
    results = []
    for name, module in checks:
        try:
            __import__(module)
            print(f"✅ {name}: 已安装")
            results.append(True)
        except ImportError as e:
            print(f"❌ {name}: 未安装 - {e}")
            results.append(False)
    
    return all(results)


async def check_services():
    """检查服务可用性"""
    print("\n" + "=" * 60)
    print("2. 检查服务配置")
    print("=" * 60)
    
    from config.settings import settings
    
    checks = [
        ("USE_MINERU", settings.use_mineru, True),
        ("NEO4J_ENABLED", settings.neo4j_enabled, True),
        ("VLM_ENABLED", getattr(settings, 'vlm_enabled', False), None),
        ("KG_QUERY_MODE", settings.kg_query_mode, "mix"),
    ]
    
    for name, actual, expected in checks:
        if expected is None:
            status = "✅" if actual else "⚠️"
            print(f"{status} {name}: {actual}")
        elif actual == expected:
            print(f"✅ {name}: {actual} (正确)")
        else:
            print(f"⚠️  {name}: {actual} (期望: {expected})")
    
    return True


async def check_structured_parser():
    """检查结构化解析服务"""
    print("\n" + "=" * 60)
    print("3. 检查结构化解析服务")
    print("=" * 60)
    
    try:
        from app.services.structured_parser import get_structured_parser_service
        
        parser = get_structured_parser_service()
        
        print(f"MinerU 可用: {'✅' if parser.mineru_available else '❌'}")
        print(f"使用 MinerU: {'✅' if parser.use_mineru else '⚠️'}")
        print(f"解析方法: {parser.mineru_method}")
        
        return parser.mineru_available
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return False


async def check_entity_extractor():
    """检查实体提取器"""
    print("\n" + "=" * 60)
    print("4. 检查实体提取器")
    print("=" * 60)
    
    try:
        from app.services.entity_extractor import get_entity_extractor
        
        extractor = get_entity_extractor()
        
        print(f"LLM API 可用: {'✅' if extractor.available else '⚠️'}")
        
        if extractor.available:
            # 简单测试并发提取
            test_chunks = [
                {"content": "机器学习是人工智能的重要分支。", "chunk_id": "test1"}
            ]
            
            result = await extractor.extract_from_chunks(test_chunks, max_chunks=1)
            print(f"并发提取测试: ✅ (提取到 {len(result.entities)} 个实体)")
            return True
        else:
            print("⚠️  LLM API 未配置,跳过实体提取测试")
            return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def check_knowledge_graph():
    """检查知识图谱服务"""
    print("\n" + "=" * 60)
    print("5. 检查知识图谱服务")
    print("=" * 60)
    
    try:
        from app.services.knowledge_graph import get_knowledge_graph_service
        
        kg_service = get_knowledge_graph_service()
        
        print(f"Neo4j 连接: {'✅' if kg_service.available else '❌'}")
        
        if kg_service.available:
            # 测试批量操作
            test_entities = [
                {"name": "TestEntity1", "type": "概念", "description": "测试"}
            ]
            
            kg_service.add_entities_batch(
                entities=test_entities,
                doc_id="quick_test",
                user_id="test_user"
            )
            print("批量添加实体: ✅")
            
            # 清理
            kg_service.delete_document_graph("quick_test", "test_user")
            print("清理测试数据: ✅")
            
            return True
        else:
            print("⚠️  Neo4j 不可用")
            return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def check_hybrid_fusion():
    """检查混合融合服务"""
    print("\n" + "=" * 60)
    print("6. 检查混合融合服务")
    print("=" * 60)
    
    try:
        from app.services.hybrid_fusion import get_query_mode_router
        from app.models.document import SearchResult
        
        router = get_query_mode_router()
        
        # 模拟测试结果
        mock_results = [
            SearchResult(
                document_id="doc1",
                chunk_id="chunk1",
                content="测试内容",
                score=0.9,
                metadata={}
            )
        ]
        
        # 测试 vector 模式
        context = await router.route(
            query="测试查询",
            user_id="test_user",
            vector_results=mock_results,
            query_mode="vector"
        )
        
        print(f"Vector 模式: ✅ (返回 {len(context)} 字符)")
        
        # 测试 mix 模式
        context = await router.route(
            query="测试查询",
            user_id="test_user",
            vector_results=mock_results,
            query_mode="mix"
        )
        
        print(f"Mix 模式: ✅ (返回 {len(context) if context else 0} 字符)")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "Memora MinerU & 知识图谱集成验证" + " " * 12 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    tests = [
        ("依赖导入", check_imports),
        ("服务配置", lambda: check_services()),
        ("结构化解析", lambda: check_structured_parser()),
        ("实体提取", lambda: check_entity_extractor()),
        ("知识图谱", lambda: check_knowledge_graph()),
        ("混合融合", lambda: check_hybrid_fusion()),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} 测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 汇总
    print("\n\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print()
    print(f"总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过!系统已准备就绪。")
        print("\n下一步:")
        print("  1. 运行: bash deploy_verify.sh 部署 Docker 环境")
        print("  2. 访问: http://localhost:8000/docs 查看 API 文档")
        print("  3. 上传 PDF 文档测试 MinerU 解析效果")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试未通过,请检查上述错误信息。")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
