import networkx as nx
import matplotlib.pyplot as plt
import pymongo
from matplotlib import rcParams

plt.rcParams['font.family'] = 'Heiti TC'
rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

client = pymongo.MongoClient("mongodb://localhost:27017/")  # 根据你的配置修改
db = client["tanpopo"]
collection = db["memory"]

def get_memory_data():
    return list(collection.find())

def visualize_memory(memories, layout_algorithm='spring_layout'):
    G = nx.Graph()

    # 创建图
    for memory in memories:
        hash = memory["hash"]
        summary = memory["summary"]
        strength = memory["strength"]
        keywords = memory["keywords"]
        create_time = memory["create_time"]

        # 添加节点，节点的label是summary，hash作为节点标识
        G.add_node(hash, label=summary, strength=strength, keywords=keywords, create_time=create_time)

        for associate in memory["associates"]:
            if associate != hash:
                G.add_edge(hash, associate)

    node_sizes = [d['strength'] * 1000 for _, d in G.nodes(data=True)]
    node_colors = [d['create_time'] for _, d in G.nodes(data=True)]  # 使用 create_time 来控制节点的颜色

    # 使用 'coolwarm' 配色方案，越强的节点颜色越接近红色
    node_color_map = plt.cm.coolwarm  # 可选择其他色图，如 'viridis', 'plasma', 'Blues', 'coolwarm' 等

    # 根据选择的布局算法计算节点位置
    if layout_algorithm == 'spring_layout':
        pos = nx.spring_layout(G, k=0.15, iterations=20)  # 弹簧布局
    elif layout_algorithm == 'circular_layout':
        pos = nx.circular_layout(G)  # 圆形布局
    elif layout_algorithm == 'spectral_layout':
        pos = nx.spectral_layout(G)  # 谱布局
    elif layout_algorithm == 'shell_layout':
        pos = nx.shell_layout(G)  # 壳布局
    elif layout_algorithm == 'planar_layout':
        pos = nx.planar_layout(G)  # 平面布局
    elif layout_algorithm == 'random_layout':
        pos = nx.random_layout(G)  # 随机布局
    elif layout_algorithm == 'kamada_kawai_layout':
        pos = nx.kamada_kawai_layout(G)  # Kamada-Kawai 布局
    else:
        raise ValueError(f"Unknown layout algorithm: {layout_algorithm}")

    # 绘制图形
    plt.figure(figsize=(24, 24))
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors, cmap=node_color_map)
    nx.draw_networkx_edges(G, pos, width=1.0, alpha=0.5, edge_color="gray")

    labels = {node: G.nodes[node]['label'] for node in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8, font_family='Heiti TC', font_color="black", 
                            verticalalignment="center", horizontalalignment="center", 
                            bbox=dict(facecolor='white', edgecolor='none', alpha=0.5))

    plt.title("记忆网络", fontsize=64, color='darkblue')

    plt.gcf().set_facecolor('whitesmoke') 

    plt.axis("off")
    plt.savefig("script/memory_network.png", dpi=600, bbox_inches='tight')

if __name__ == "__main__":
    visualize_memory(get_memory_data(), layout_algorithm='kamada_kawai_layout')
