r"""
Vis multi dataset and their connection
"""
from typing import List, Mapping, Optional, Union
import random

from anndata import AnnData
from sklearn.metrics.pairwise import euclidean_distances
import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
import plotly.graph_objects as go


def random_color(n=1,seed:int=0):
    r"""
    Get color randomly
    
    Parameters
    ---------
    n
        number of colors you want
    seed
        seed to duplicate
    """
    random.seed(seed)
    if n==1:
        return "#"+''.join([random.choice('0123456789ABCDEF') for j in range(6)])
    elif n>1 :
        return ["#"+''.join([random.choice('0123456789ABCDEF') for j in range(6)]) for i in range(n)]


class build_3D():
    r"""
    Build 3D pics/models from multi-datasets
    
    Parameters
    ---------
    datasets
        list adata of in order
    mappings
        list of SLAT results
    spatial_key
        obsm key of spatial info
    anno_key
        obs key of cell annotation such as celltype
    subsample_size
        subsample size of matches
    scale_coordinate
        scale the coordinate from different slides
    smooth
        use spatial info to smooth mapping (experimental)
    range
        top K of the mapping which can be smoothed  
    mapping_rank_list
        index of the mapping via cos similarity
    """
    def __init__(self,adatas:List[AnnData],
               mappings:List[np.ndarray],
               spatial_key:Optional[str]='spatial',
               anno_key:Optional[str]='annotation',
               subsample_size:Optional[int]=200,
               scale_coordinate:Optional[bool]=True,
               smooth:Optional[bool]=False,
               range:Optional[int]=10,
               mapping_rank_list:Optional[List[np.ndarray]]=None
        ) -> None:
        assert len(mappings) == len(adatas) - 1
        self.smooth = smooth
        if self.smooth:
            self.range = range
            assert mapping_rank_list != None
            self.mapping_rank_list = mapping_rank_list
        
        self.mappings=mappings
        self.loc_list = []
        self.anno_list = []
        for adata in adatas:
            loc = adata.obsm[spatial_key]
            if scale_coordinate:
                for i in range(2):
                    loc[:,i] = (loc[:,i]-np.min(loc[:,i]))/(np.max(loc[:,i])-np.min(loc[:,i]))
            anno = adata.obs[anno_key]
            self.loc_list.append(loc)
            self.anno_list.append(anno)
            
        self.celltypes = set(pd.concat(self.anno_list))
        self.subsample_size = subsample_size
            
    def draw_3D(self,
                size: Optional[List[int]]=[10,10],
                point_size: Optional[List[int]]=[0.5,0.5],
                point_alpha: Optional[float]=0.6,
                line_width: Optional[float]=0.6,
                line_color: Optional[str]='#4169E1',
                line_alpha: Optional[float]=0.8,
                hide_axis: Optional[bool]=False,
                height: Optional[float]=1.0
        ) -> None:
        r"""
        Draw 3D picture of two layers
        
        Parameters:
        ----------
        size
            plt figure size
        point_size
            point size of every layer
        line_width
            pair line width 
        hide_axis
            if hide axis
        height
            height of one layer
        """
        fig = plt.figure(figsize=(size[0],size[1]))
        ax = fig.add_subplot(111, projection='3d')
        ax.set_box_aspect([5,5,8])
        # color by different cell types
        color = random_color(len(self.celltypes))
        c_map = {}
        for i, celltype in enumerate(self.celltypes):
            c_map[celltype] = color[i]
        for j, mapping in enumerate(self.mappings):
            print(f"Mapping {j}th layer ")
            # plot cells
            for i, (layer, anno) in enumerate(zip(self.loc_list[j:j+2], self.anno_list[j:j+2])):
                if i==0 and 0<j<len(self.mappings)-1:
                    continue
                    # print('test')
                for cell_type in self.celltypes:
                    slice = layer[anno == cell_type,:]
                    xs = slice[:,0]
                    ys = slice[:,1]
                    zs = height*(j+i)
                    ax.scatter(xs, ys, zs, s=point_size[i], c=c_map[cell_type], alpha=point_alpha)
            # plot mapping line
            mapping = mapping[:,np.random.choice(mapping.shape[1], self.subsample_size, replace=False)].copy()
            for k in range(mapping.shape[1]):
                cell1_index = mapping[:,k][0]  # query
                if self.smooth:  # ref list
                    mapping_rank = self.mapping_rank_list[j][cell1_index,:]
                    cell0_index = self.smooth_mapping(cell1_index,mapping_rank,j)
                else:  # precise map
                    cell0_index = mapping[:,k][1] # ref
                cell0_coord = self.loc_list[j][cell0_index,:]
                cell1_coord = self.loc_list[j+1][cell1_index,:]
                coord = np.row_stack((cell0_coord,cell1_coord))
                ax.plot(coord[:,0], coord[:,1], [height*j,height*(j+1)], color=line_color, linestyle="dashed", linewidth=line_width,alpha=line_alpha)

        if hide_axis:
            plt.axis('off')
        plt.show()

    def smooth_mapping(self,
        query:int,
        ref_list:List[int],
        layer:int,
        range:Optional[int]=20
        )->np.ndarray:
        r"""
        Use smoothed cell mapping to replace the best cell mapping 
        
        Parameters
        ----------
        query
            query cell index
        ref_list
            reference cell index list
        layer
            query cell layer (assume)
        range
            top K of the mapping which can be smoothed 
        """
        assert 1 <= range <= len(ref_list)
        ref_list = ref_list[0:range]
        dis = euclidean_distances(self.loc_list[layer][query,:], self.loc_list[layer+1][ref_list,:])
        best = ref_list[np.argmin(dis)]
        return best


class match_3D_multi():
    r"""
    Plot the mapping result between 2 datasets
    
    Parameters
    ---------
    dataset_A
        pandas dataframe which contain ['index','x','y'], reference dataset
    dataset_B
        pandas dataframe which contain ['index','x','y'], target dataset
    matching
        matching results
    meta
        dataframe colname of meta, such as celltype
    expr
        dataframe colname of gene expr
    subsample_size
        subsample size of matches
    reliability
        match score (cosine similarity score)
    scale_coordinate
        if scale coordinate via (:math:`data - np.min(data)) / (np.max(data) - np.min(data))`)
    rotate
        how to rotate the slides (force scale_coordinate), such as ['x','y'], means dataset0 rotate on x axes
        and dataset1 rotate on y axes
    change_xy
        exchange x and y on dataset_B

    Note
    ----------
    dataset_A and dataset_B can in different length
        
    """
    def __init__(self,dataset_A:pd.DataFrame,
                 dataset_B: pd.DataFrame,
                 matching: np.ndarray,
                 meta: Optional[str]=None,
                 expr: Optional[str]=None,
                 subsample_size: Optional[int]=300,
                 reliability: Optional[np.ndarray]=None,
                 scale_coordinate: Optional[bool]=True,
                 rotate: Optional[List[str]]=None,
                 exchange_xy: Optional[bool]=False
        ) -> None:
        self.dataset_A = dataset_A.copy()
        self.dataset_B = dataset_B.copy()
        self.meta = meta
        self.matching= matching
        self.conf = reliability
        scale_coordinate = True if rotate != None else scale_coordinate
        
        assert all(item in dataset_A.columns.values for item in ['index','x','y'])
        assert all(item in dataset_B.columns.values for item in ['index','x','y'])
        
        if meta:
            self.celltypes = set(self.dataset_A[meta].append(self.dataset_B[meta]))
            set1 = list(set(self.dataset_A[meta]))
            set2 = list(set(self.dataset_B[meta]))
            overlap = [x for x in set2 if x in set1]
            print(f"dataset1: {len(set1)} cell types; dataset2: {len(set2)} cell types; \n\
                    Total :{len(self.celltypes)} celltypes; Overlap: {len(overlap)} cell types \n\
                    Not overlap :[{[y for y in (set1+set2) if y not in overlap]}]"
                    )
        self.expr = expr if expr else False
            
        if scale_coordinate:
            for i, dataset in enumerate([self.dataset_A, self.dataset_B]):
                for axis in ['x','y']:
                    dataset[axis] = (dataset[axis] - np.min(dataset[axis])) / (np.max(dataset[axis])- np.min(dataset[axis]))
                    if rotate == None:
                        pass
                    elif axis in rotate[i]:
                        dataset[axis] = 1 - dataset[axis]
        if exchange_xy:
            self.dataset_B[['x','y']] = self.dataset_B[['y','x']]

        subsample_size = subsample_size if matching.shape[1] > subsample_size else matching.shape[1]
        print(f'Subsample {subsample_size} cell pairs from {matching.shape[1]}')
        self.matching = matching[:,np.random.choice(matching.shape[1],subsample_size, replace=False)]
            
        self.datasets = [self.dataset_A, self.dataset_B]
    
    def draw_3D(self,
                size: Optional[List[int]]=[10,10],
                point_size: Optional[List[int]]=[0.1,0.1],
                line_width: Optional[float]=0.3,
                line_color:Optional[str]='grey',
                line_alpha: Optional[float]=0.7,
                hide_axis: Optional[bool]=False,
                show_error: Optional[bool]=True,
                cmap: Optional[bool]='Reds',
                save:Optional[str]=None
        ) -> None:
        r"""
        Draw 3D picture of two datasets
        
        Parameters:
        ----------
        size
            plt figure size
        point_size
            point size of every dataset
        line_width
            pair line width
        line_color
            pair line color
        line_alpha
            pair line alpha
        hide_axis
            if hide axis
        show_error
            if show error celltype mapping with different color
        cmap
            color map when vis expr
        save
            save file path
        """
        show_error = show_error if self.meta else False
        fig = plt.figure(figsize=(size[0],size[1]))
        ax = fig.add_subplot(111, projection='3d')
        # color by different cell types
        if self.meta:
            color = random_color(len(self.celltypes))
            c_map = {}
            for i, celltype in enumerate(self.celltypes):
                c_map[celltype] = color[i]
            if self.expr:
                c_map = cmap
                # expr_concat = pd.concat(self.datasets)[self.expr].to_numpy()
                # norm = plt.Normalize(expr_concat.min(), expr_concat.max())
            for i, dataset in enumerate(self.datasets):
                if self.expr:
                    norm = plt.Normalize(dataset[self.expr].to_numpy().min(), dataset[self.expr].to_numpy().max())
                for cell_type in self.celltypes:
                    slice = dataset[dataset[self.meta] == cell_type]
                    xs = slice['x']
                    ys = slice['y']
                    zs = i
                    if self.expr:
                        ax.scatter(xs, ys, zs, s=point_size[i], c=slice[self.expr], cmap=c_map,norm=norm)
                    else:
                        ax.scatter(xs, ys, zs, s=point_size[i], c=c_map[cell_type])
                    
        # plot different point layers
        else:
            for i, dataset in enumerate(self.datasets):
                xs = dataset['x']
                ys = dataset['y']
                zs = i
                ax.scatter(xs,ys,zs,s=point_size[i])
        
        # plot line
        self.draw_lines(ax, show_error, line_color, line_width, line_alpha)
        if hide_axis:
            plt.axis('off')
        if save != None:
            plt.savefig(save)
        plt.show()

        
    def draw_lines(self, ax, show_error, default_color, line_width=0.3, line_alpha=0.7) -> None:
        r"""
        Draw lines between paired cells in two datasets
        """
        for i in range(self.matching.shape[1]):
            pair = self.matching[:,i]
            default_color = default_color
            if self.meta != None:
                if self.dataset_B.loc[self.dataset_B['index']==pair[0], self.meta].astype(str).values ==\
                    self.dataset_A.loc[self.dataset_A['index']==pair[1], self.meta].astype(str).values:
                    color = '#ade8f4' # blue
                else:
                    color = '#ffafcc'  # red
                if self.conf:
                    if color == '#ade8f4' and not self.conf[i]: # low reliability but right
                        color = '#588157' # green
                    elif color == '#ffafcc' and self.conf[i]: # high reliability but error
                        color = '#ffb703' # yellow
                
            point0 = np.append(self.dataset_A[self.dataset_A['index']==pair[1]][['x','y']], 0)
            point1 = np.append(self.dataset_B[self.dataset_B['index']==pair[0]][['x','y']], 1)
            coord = np.row_stack((point0,point1))
            color = color if show_error else default_color
            ax.plot(coord[:,0], coord[:,1], coord[:,2], color=color, linestyle="dashed", linewidth=line_width, alpha=line_alpha)


class match_3D_multi_error(match_3D_multi):
    r"""
    Highlight the error mapping between datasets, child of class:`match_3D_multi()`
    
    Parameters
    ---------
    dataset_A
        pandas dataframe which contain ['index','x','y']
    dataset_B
        pandas dataframe which contain ['index','x','y']
    matching
        matching results
    mode
        which cell pairs to highlight
    highlight_color
        color to highlight the line 
    meta
        dataframe colname of meta, such as celltype
    expr
        dataframe colname of gene expr
    subsample_size
        subsample size of matches
    reliability
        if the match is reliable
    scale_coordinate
        if scale the coordinate via `data - np.min(data)) / (np.max(data) - np.min(data))` 
    rotate
        how to rotate the slides (force scale_coordinate)
    change_xy
        exchange x and y on dataset_B
        
    Note
    ----------
    dataset_A and dataset_B can in different length
        
    """
    def __init__(self,dataset_A: pd.DataFrame,
                 dataset_B: pd.DataFrame,
                 matching: np.ndarray,
                 mode: Optional[str]='high_true',
                 highlight_color: Optional[str]='red',
                 meta: Optional[str]=None,
                 expr: Optional[str]=None,
                 subsample_size: Optional[int]=300,
                 reliability: Optional[np.ndarray]=None,
                 scale_coordinate: Optional[bool]=False,
                 rotate: Optional[List[str]]=None,
                 exchange_xy: Optional[bool]=False,
        ) -> None:
        super(match_3D_multi_error, self).__init__(dataset_A,dataset_B,matching,meta,expr,subsample_size,reliability,
                                                   scale_coordinate,rotate,exchange_xy)
        assert mode in ['high_true','low_true','high_false','low_false']
        self.mode = mode
        self.highlight_color = highlight_color
        
    def draw_lines(self,ax,show_error,default_color,line_width=0.3,line_alpha=0.7) -> None:
        for i in range(self.matching.shape[1]):
            pair = self.matching[:,i]
            if self.dataset_B.loc[self.dataset_B['index']==pair[0], 'celltype'].astype(str).values ==\
                self.dataset_A.loc[self.dataset_A['index']==pair[1],'celltype'].astype(str).values:
                if 'false' in self.mode:
                    continue
            if not self.conf is None:
                if 'low' in self.mode and not self.conf[i]: 
                    continue
            point0 = np.append(self.dataset_A[self.dataset_A['index']==pair[1]][['x','y']], 0)
            point1 = np.append(self.dataset_B[self.dataset_B['index']==pair[0]][['x','y']], 1)
            coord = np.row_stack((point0,point1))
            ax.scatter(point0[0],point0[1],point0[2],color='red',alpha=1,s=0.3)
            ax.scatter(point1[0],point1[1],point1[2],color='red',alpha=1,s=0.3)
            ax.plot(coord[:,0], coord[:,1], coord[:,2], color=self.highlight_color, linestyle="dashed",linewidth=line_width,alpha=line_alpha)


class match_3D_celltype(match_3D_multi):
    r"""
    Highlight the celltype mapping, child of class:`match_3D_multi()`
    
    Parameters
    ---------
    dataset_A
        pandas dataframe which contain ['index','x','y']
    dataset_B
        pandas dataframe which contain ['index','x','y']
    matching
        matching results
    highlight_celltype
        celltypes to highlight in two datasets
    highlight_line
        color to highlight the line
    highlight_cell
        color to highlight the cell
    meta
        dataframe colname of meta, such as celltype
    expr
        dataframe colname of gene expr
    subsample_size
        subsample size of matches
    reliability
        if the match is reliable
    scale_coordinate
        if scale the coordinate via `data - np.min(data)) / (np.max(data) - np.min(data))` 
    rotate
        how to rotate the slides (force scale_coordinate)
    change_xy
        exchange x and y on dataset_B
        
    Note
    ----------
    dataset_A and dataset_B can in different length
    """
    def __init__(self,dataset_A: pd.DataFrame,
                 dataset_B: pd.DataFrame,
                 matching: np.ndarray,
                 highlight_celltype: Optional[List[List[str]]]=[[],[]],
                 highlight_line: Optional[Union[List[str],str]]='red',
                 highlight_cell: Optional[str]=None,
                 meta: Optional[str]=None,
                 expr: Optional[str]=None,
                 subsample_size: Optional[int]=300,
                 reliability: Optional[np.ndarray]=None,
                 scale_coordinate: Optional[bool]=False,
                 rotate: Optional[List[str]]=None,
                 exchange_xy: Optional[bool]=False,
        ) -> None:
        super(match_3D_celltype, self).__init__(dataset_A,dataset_B,matching,meta,expr,subsample_size,reliability,
                                                   scale_coordinate,rotate,exchange_xy)
        assert set(highlight_celltype[0]).issubset(set(self.celltypes))
        assert set(highlight_celltype[1]).issubset(set(self.celltypes))
        self.highlight_celltype = highlight_celltype
        self.highlight_line = highlight_line
        self.highlight_cell = highlight_cell
        
    def draw_lines(self,ax,show_error,default_color,line_width=0.3,line_alpha=0.7)-> None:
        color_index = self.highlight_celltype[0] if len(self.highlight_celltype[0]) >= len(self.highlight_celltype[1]) else self.highlight_celltype[1]
        if type(self.highlight_line) == list and len(self.highlight_line) >= len(color_index):
            cmap = self.highlight_line
        else:
            cmap = random_color(len(color_index))
        
        for i in range(self.matching.shape[1]):
            pair = self.matching[:,i]
            a = self.dataset_A.loc[self.dataset_A['index']==pair[1], self.meta].astype(str).values
            b = self.dataset_B.loc[self.dataset_B['index']==pair[0], self.meta].astype(str).values
            if a not in self.highlight_celltype[0] or b not in self.highlight_celltype[1]:
                continue
            color = cmap[color_index.index(a)] if len(self.highlight_celltype[0]) >= len(self.highlight_celltype[1]) else cmap[color_index.index(b)]
            point0 = np.append(self.dataset_A[self.dataset_A['index']==pair[1]][['x','y']], 0)
            point1 = np.append(self.dataset_B[self.dataset_B['index']==pair[0]][['x','y']], 1)
            coord = np.row_stack((point0,point1))
            if self.highlight_cell:
                ax.scatter(point0[0],point0[1],point0[2],color=self.highlight_cell,alpha=1,s=1)
                ax.scatter(point1[0],point1[1],point1[2],color=self.highlight_cell,alpha=1,s=1)
            color = color if show_error else default_color
            ax.plot(coord[:,0], coord[:,1], coord[:,2], color=color, linestyle="dashed",linewidth=line_width, alpha=line_alpha)



def Sankey(matching_table:pd.DataFrame,
           color:Optional[List[str]]='red',
           title:Optional[str]='Sankey plot',
           prefix:Optional[List[str]]=['E11.5','E12.5'],
           layout:Optional[List[int]]=[1300,900],
           font_size:Optional[float]=15,
           font_color:Optional[str]='Black'):
    r"""
    Sankey plot of celltype
    
    Parameters
    ----------
    matching_tables
        list of matching table
    color
        color of node
    title
        plot title
    prefix
        prefix to distinguish datasets
    layout
        layout size of picture
    font_size
        font size in plot
    font_color
        font color in plot
    """
    source, target, value = [], [], []
    label_ref = [a + f'_{prefix[0]}' for a in matching_table.columns.to_list()]
    label_query = [a + f'_{prefix[1]}' for a in matching_table.index.to_list()]
    label_all = label_query + label_ref
    label2index = dict(zip(label_all, list(range(len(label_all)))))
    
    for i, query in enumerate(label_query):
        for j, ref in enumerate(label_ref):
            if int(matching_table.iloc[i,j]) > 10:
                target.append(label2index[query])
                source.append(label2index[ref])
                value.append(int(matching_table.iloc[i,j]))

    fig = go.Figure(data=[go.Sankey(
        node = dict(
          pad = 50,
          thickness = 50,
          line = dict(color = "green", width = 0.5),
          label = label_all,
          color = color
        ),
        link = dict(
          source = source, # indices correspond to labels, eg A1, A2, A1, B1, ...
          target = target,
          value = value
      ))],layout=go.Layout(autosize=False, width=layout[0], height=layout[1])
                   )

    fig.update_layout(title_text=title, font_size=font_size, font_color=font_color)
    fig.show()
    

def multi_Sankey(matching_tables:List[pd.DataFrame],
                color:Optional[List[str]]='random',
                title:Optional[str]='Sankey plot',
                layout:Optional[List[int]]=[1300,900],
                day:Optional[float]=11.5):
    r"""
    Sankey plot of celltype in multi datasets
    
    Parameters
    ----------
    matching_tables
        list of matching table
    color
        color of node
    title
        plot title
    day
        start day of dataset
    """
    mappings = len(matching_tables) + 1
    prefixes = [day + i for i in range(mappings)]
    source, target, value, label_all= [], [], [], set()
    for i, matching_table in enumerate(matching_tables):
        label_ref = [a + f'_{prefixes[i]}' for a in matching_table.columns.to_list()]
        label_query = [a + f'_{prefixes[i+1]}' for a in matching_table.index.to_list()]
        # label_all.add(label_ref)
        for i in label_ref+label_query:
            label_all.add(i) 
    label2index = dict(zip(label_all, list(range(len(label_all)))))
    
    for matching_table,prefix in zip(matching_tables,prefixes):
        for i, query in enumerate(matching_table.index):
            for j, ref in enumerate(matching_table.columns):
                if int(matching_table.iloc[i,j]) > 10:
                    target.append(label2index[query+'_'+str(prefix+1)])
                    source.append(label2index[ref+'_'+str(prefix)])
                    value.append(int(matching_table.iloc[i,j]))
                    
    if color == 'random':
        color = [random_color()]*matching_tables[0].shape[0]
        for matching_table in matching_tables:
            color += [random_color()]*matching_table.shape[1]

    fig = go.Figure(data=[go.Sankey(
        node = dict(
          pad = 50,
          thickness = 50,
          line = dict(color="green", width=0.5),
          label = list(label_all),
          color = color
        ),
        link = dict(
          source = source, # indices correspond to labels, eg A1, A2, A1, B1, ...
          target = target,
          value = value
      ))],layout=go.Layout(autosize=False, width=layout[0], height=layout[1])
                   )

    fig.update_layout(title_text=title, font_size=10)
    fig.show()